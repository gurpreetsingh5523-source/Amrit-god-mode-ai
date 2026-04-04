"""Dataset Agent — Load, clean, analyze, build, enrich, and export datasets."""
import json
from pathlib import Path
from base_agent import BaseAgent

class DatasetAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("DatasetAgent", eb, state)
        Path("datasets").mkdir(exist_ok=True)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "load")
        await self.report(f"Dataset [{action}]: {d.get('dataset', d.get('topic', ''))}")
        ops = {
            "load": self._load, "clean": self._clean, "analyze": self._analyze,
            "export": self._export, "build": self._build, "sample": self._sample,
            "enrich": self._enrich, "research_dataset": self._research_dataset,
            "validate": self._validate_dataset, "merge": self._merge,
        }
        return await ops.get(action, self._load)(d)

    async def _load(self, d):
        p = Path(d.get("dataset",""))
        if not p.exists(): return self.err(f"Not found: {p}")
        try:
            import pandas as pd
            ext = p.suffix.lower()
            loaders = {".csv":pd.read_csv,".json":pd.read_json,".xlsx":pd.read_excel,
                       ".parquet":pd.read_parquet,".tsv":lambda f:pd.read_csv(f,sep="\t")}
            loader = loaders.get(ext)
            if not loader: return self.err(f"Unsupported: {ext}")
            df = loader(p)
            return self.ok(rows=len(df),columns=list(df.columns),
                           dtypes={c:str(t) for c,t in df.dtypes.items()},
                           head=df.head(5).to_dict())
        except ImportError: return self.err("pip install pandas openpyxl")
        except Exception as e: return self.err(str(e))

    async def _clean(self, d):
        p = Path(d.get("dataset",""))
        try:
            import pandas as pd
            df = pd.read_csv(p); before = len(df)
            df.drop_duplicates(inplace=True)
            df.dropna(how="all",inplace=True)
            out = d.get("output", str(p).replace(".","_clean."))
            df.to_csv(out, index=False)
            return self.ok(before=before,after=len(df),removed=before-len(df),output=out)
        except Exception as e: return self.err(str(e))

    async def _analyze(self, d):
        p = Path(d.get("dataset",""))
        try:
            import pandas as pd
            df = pd.read_csv(p)
            nulls = df.isnull().sum().to_dict()
            insight = await self.ask_llm(
                f"Dataset: {len(df)} rows, columns: {list(df.columns)}, nulls: {nulls}. "
                "What analysis would be most valuable?")
            return self.ok(shape=list(df.shape),nulls=nulls,insight=insight)
        except Exception as e: return self.err(str(e))

    async def _export(self, d):
        p = Path(d.get("dataset","")); fmt = d.get("format","csv")
        out = Path(d.get("output",f"workspace/export.{fmt}"))
        try:
            import pandas as pd; out.parent.mkdir(exist_ok=True)
            df = pd.read_csv(p)
            {"json":lambda:df.to_json(out,orient="records",indent=2),
             "xlsx":lambda:df.to_excel(out,index=False),
             "parquet":lambda:df.to_parquet(out)}.get(fmt, lambda:df.to_csv(out,index=False))()
            return self.ok(output=str(out),format=fmt,rows=len(df))
        except Exception as e: return self.err(str(e))

    async def _build(self, d):
        topic = d.get("topic","general"); n = int(d.get("n",50))
        prompt = f"Generate {n} diverse training examples for: {topic}\nReturn JSON array of objects with 'input' and 'output' keys."
        data = await self.ask_llm(prompt, max_tokens=3000)
        out = Path(f"datasets/{topic.replace(' ','_')}.json")
        out.parent.mkdir(exist_ok=True); out.write_text(data)
        return self.ok(topic=topic, generated=n, file=str(out))

    async def _sample(self, d):
        p = Path(d.get("dataset","")); n = int(d.get("n",10))
        try:
            import pandas as pd
            df = pd.read_csv(p).sample(min(n,len(pd.read_csv(p))))
            return self.ok(n=len(df),sample=df.to_dict())
        except Exception as e: return self.err(str(e))

    # ══════════════════════════════════════════════════════════════
    # NEW: Dataset Enrichment & Research
    # ══════════════════════════════════════════════════════════════

    async def _enrich(self, d):
        """Enrich an existing dataset with LLM-generated additional columns."""
        p = Path(d.get("dataset", ""))
        new_columns = d.get("columns", [])
        if not p.exists():
            return self.err(f"Not found: {p}")
        try:
            import pandas as pd
            df = pd.read_csv(p)
            if not new_columns:
                # Ask LLM what columns would be valuable
                suggestion = await self.ask_llm(
                    f"Dataset has columns: {list(df.columns)} with {len(df)} rows.\n"
                    f"Sample: {df.head(3).to_dict()}\n"
                    "Suggest 3 useful derived columns to add. Return as JSON array of strings."
                )
                import re
                m = re.search(r'\[.*?\]', suggestion, re.DOTALL)
                if m:
                    try:
                        new_columns = json.loads(m.group(0))
                    except Exception:
                        new_columns = ["category", "quality_score", "summary"]
                else:
                    new_columns = ["category", "quality_score", "summary"]

            # Generate enrichment for each new column (subset for speed)
            sample_n = min(20, len(df))
            for col in new_columns[:3]:
                values = []
                for i, row in df.head(sample_n).iterrows():
                    val = await self.ask_llm(
                        f"For this data row: {row.to_dict()}\n"
                        f"Generate the value for column '{col}'. Return ONLY the value, nothing else.",
                        max_tokens=100
                    )
                    values.append(val.strip())
                # Fill only the sample rows
                df.loc[:sample_n-1, col] = values

            out = str(p).replace(".", "_enriched.")
            df.to_csv(out, index=False)
            return self.ok(original=str(p), enriched=out,
                           new_columns=new_columns[:3], rows=len(df))
        except ImportError:
            return self.err("pip install pandas")
        except Exception as e:
            return self.err(str(e))

    async def _research_dataset(self, d):
        """Build a high-quality research dataset for a scientific topic."""
        topic = d.get("topic", "general science")
        n = int(d.get("n", 30))
        categories = d.get("categories", ["question", "answer", "source", "confidence", "domain"])

        prompt = f"""Generate a high-quality scientific research dataset about: {topic}

Create {n} entries as a JSON array. Each entry must have these fields:
{json.dumps(categories)}

Requirements:
- Questions should be factual and testable
- Answers should include specific numbers, dates, or mechanisms
- Source should reference real scientific concepts
- Confidence should be high/medium/low
- Domain should specify the scientific field

Return ONLY the JSON array."""

        data = await self.ask_llm(prompt, max_tokens=3000)

        # Parse and save
        import re
        clean = re.sub(r"```(?:json)?|```", "", data).strip()
        match = re.search(r'\[.*\]', clean, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                parsed = [{"raw": data}]
        else:
            parsed = [{"raw": data}]

        safe_topic = "".join(c if c.isalnum() or c == "_" else "_" for c in topic)[:30]
        out = Path(f"datasets/research_{safe_topic}.json")
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))

        return self.ok(topic=topic, generated=len(parsed), file=str(out),
                       categories=categories)

    async def _validate_dataset(self, d):
        """Validate dataset quality — check for errors, biases, completeness."""
        p = Path(d.get("dataset", ""))
        if not p.exists():
            return self.err(f"Not found: {p}")
        try:
            import pandas as pd
            df = pd.read_csv(p)
            nulls = df.isnull().sum().to_dict()
            dtypes = {c: str(t) for c, t in df.dtypes.items()}
            dupes = int(df.duplicated().sum())

            analysis = await self.ask_llm(
                f"""Validate this dataset for research quality:

Columns: {list(df.columns)}
Rows: {len(df)}
Nulls: {nulls}
Types: {dtypes}
Duplicates: {dupes}
Sample: {df.head(5).to_dict()}

Check for:
1. DATA_QUALITY: Missing values, inconsistencies, outliers
2. BIAS: Any sampling or representation bias?
3. COMPLETENESS: Are all necessary fields present?
4. ACCURACY: Do the values seem reasonable?
5. RECOMMENDATIONS: How to improve this dataset
6. SCORE: Rate dataset quality 0-100""")

            return self.ok(rows=len(df), columns=list(df.columns),
                           nulls=nulls, duplicates=dupes, validation=analysis)
        except ImportError:
            return self.err("pip install pandas")
        except Exception as e:
            return self.err(str(e))

    async def _merge(self, d):
        """Merge multiple datasets."""
        files = d.get("files", [])
        if not files:
            return self.err("No files to merge")
        try:
            import pandas as pd
            dfs = []
            for f in files:
                p = Path(f)
                if p.exists():
                    dfs.append(pd.read_csv(p))
            if not dfs:
                return self.err("No valid files found")
            merged = pd.concat(dfs, ignore_index=True)
            out = d.get("output", "datasets/merged.csv")
            Path(out).parent.mkdir(exist_ok=True)
            merged.to_csv(out, index=False)
            return self.ok(files_merged=len(dfs), total_rows=len(merged), output=out)
        except Exception as e:
            return self.err(str(e))
