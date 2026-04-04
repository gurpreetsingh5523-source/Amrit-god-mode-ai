"""Dataset Trainer — Fine-tunes local models on agent-generated data."""
from pathlib import Path
from logger import setup_logger
logger = setup_logger("DatasetTrainer")

class DatasetTrainer:
    def __init__(self, model="microsoft/phi-2", output="workspace/fine_tuned"):
        self.model = model; self.output = output

    async def train(self, dataset_path: str, epochs=3, lr=2e-4, batch=4) -> dict:
        try:
            from transformers import (AutoModelForCausalLM, AutoTokenizer,
                                      TrainingArguments, Trainer, DataCollatorForLanguageModeling)
            from datasets import load_dataset
            tokenizer = AutoTokenizer.from_pretrained(self.model)
            model     = AutoModelForCausalLM.from_pretrained(self.model)
            ds = load_dataset("json", data_files=dataset_path, split="train")
            tokenized = ds.map(lambda ex: tokenizer(ex["text"],truncation=True,max_length=512),
                               batched=True, remove_columns=ds.column_names)
            args = TrainingArguments(output_dir=self.output,num_train_epochs=epochs,
                                     per_device_train_batch_size=batch,learning_rate=lr,
                                     save_steps=100,logging_steps=10)
            Trainer(model=model,args=args,train_dataset=tokenized,
                    data_collator=DataCollatorForLanguageModeling(tokenizer,mlm=False)).train()
            model.save_pretrained(self.output); tokenizer.save_pretrained(self.output)
            return {"status":"trained","output":self.output}
        except ImportError as e:
            return {"status":"error","error":f"Missing: {e} — pip install transformers datasets torch"}
        except Exception as e:
            return {"status":"error","error":str(e)}

    def prepare_jsonl(self, items: list, path="datasets/train.jsonl") -> str:
        import json
        Path(path).parent.mkdir(exist_ok=True)
        with open(path,"w") as f:
            for item in items: json.dump(item,f); f.write("\n")
        return path
