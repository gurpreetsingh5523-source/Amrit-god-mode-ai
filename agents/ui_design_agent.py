"""
UI Design Agent — Beautiful UI generation with design sense.

Uses design system knowledge (shadcn/ui, Tailwind, Radix) to generate
production-quality UIs. Bridges the gap between "works" and "looks great".

Capabilities:
  - Generate UI wireframes → code
  - Create landing pages, dashboards, forms
  - Color palette + typography recommendations
  - Responsive layouts
  - Dark mode support
  - Animation with Framer Motion
  - Design critique and improvement
"""
from pathlib import Path
from base_agent import BaseAgent


UI_DESIGN_PROMPT = """You are a world-class UI/UX designer AND developer.
Design philosophy:
- Clean, modern, minimal but not empty
- Consistent spacing (4px grid: p-1=4px, p-2=8px, p-4=16px, p-8=32px)
- Typography hierarchy: text-4xl bold for headlines, text-lg for subheads, text-base for body
- Color: use semantic colors (primary, secondary, muted, accent) — never hardcode hex
- Shadows: subtle (shadow-sm, shadow-md) — never overdone
- Borders: border-border, rounded-lg for cards, rounded-full for pills
- Animation: subtle transitions (transition-all duration-200)
- Dark mode: use dark: variants throughout

shadcn/ui components to use: Button, Card, CardHeader, CardContent, Input, Badge,
Avatar, Tabs, Dialog, Sheet, Dropdown, Command, Toast, Tooltip, Progress

TailwindCSS patterns:
- Cards: <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
- Buttons: use shadcn Button with variant="default|outline|ghost|destructive"
- Layout: flex, grid, gap-4, max-w-7xl mx-auto px-4
"""

LANDING_PAGE_SECTIONS = [
    "navbar",
    "hero",
    "features",
    "how_it_works",
    "pricing",
    "testimonials",
    "cta",
    "footer"
]


class UIDesignAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("UIDesignAgent", eb, state)

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "generate")

        if action == "landing_page":
            return await self._landing_page(
                d.get("product", ""),
                d.get("description", ""),
                d.get("color_scheme", "blue")
            )
        if action == "dashboard":
            return await self._dashboard(
                d.get("name", ""),
                d.get("metrics", []),
                d.get("sections", [])
            )
        if action == "component":
            return await self._ui_component(
                d.get("name", ""),
                d.get("description", "")
            )
        if action == "critique":
            return await self._critique(d.get("code", ""))
        if action == "color_palette":
            return await self._color_palette(d.get("brand", ""))
        return await self._generate_ui(task.get("name", ""))

    async def _landing_page(self, product: str, description: str, color: str) -> dict:
        """Generate a complete, beautiful landing page."""
        prompt = f"""{UI_DESIGN_PROMPT}

Create a STUNNING, production-quality Next.js landing page for:
Product: {product}
Description: {description}
Color scheme: {color}

Generate the complete page.tsx with ALL sections:
1. Sticky navbar with logo, nav links, CTA button
2. Hero with gradient background, big headline, subtext, two CTAs, mockup image placeholder
3. Features grid (3 cols) with icons (use lucide-react)
4. Social proof / stats bar (3-4 numbers)
5. How it works (3 steps with numbers)
6. Pricing cards (Free / Pro / Enterprise)
7. Big CTA section with gradient
8. Footer with links

Requirements:
- TypeScript TSX
- All shadcn/ui components
- Beautiful gradient: bg-gradient-to-br from-{color}-50 to-{color}-100
- Animated hero text
- Dark mode ready
- Mobile responsive
- Realistic copy (not Lorem ipsum)
- lucide-react icons throughout

Return ONLY the complete TSX code."""

        code = await self.ask_llm(prompt, max_tokens=4000)
        out = Path(f"workspace/ui/landing_{product.replace(' ', '_').lower()}.tsx")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
        return self.ok(product=product, path=str(out), lines=len(code.splitlines()))

    async def _dashboard(self, name: str, metrics: list, sections: list) -> dict:
        """Generate a beautiful analytics dashboard."""
        default_metrics = metrics or ["Total Users", "Revenue", "Active Sessions", "Growth Rate"]
        prompt = f"""{UI_DESIGN_PROMPT}

Create a beautiful, data-rich dashboard page for: "{name}"
Key metrics to show: {', '.join(default_metrics)}
Sections: {', '.join(sections) if sections else 'Overview, Analytics, Recent Activity, Settings'}

Include:
- Sidebar navigation with icons (lucide-react)
- Top header with user avatar, notifications
- Metric cards with trend indicators (↑↓ with color)
- Recharts or shadcn chart placeholders
- Recent activity table
- Quick actions panel

Use a professional dark sidebar (bg-gray-900) + light main content layout.
Return ONLY complete TSX code."""

        code = await self.ask_llm(prompt, max_tokens=4000)
        out = Path(f"workspace/ui/dashboard_{name.replace(' ', '_').lower()}.tsx")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
        return self.ok(name=name, path=str(out))

    async def _ui_component(self, name: str, description: str) -> dict:
        """Generate a single polished UI component."""
        prompt = f"""{UI_DESIGN_PROMPT}

Design and implement a beautiful "{name}" component.
Purpose: {description}

Requirements:
- TypeScript with full type safety
- Multiple variants (default, outlined, minimal)
- Hover/focus/active states
- Accessible (aria attributes)
- Animated micro-interactions
- Dark mode support

Return ONLY the TSX component code."""

        code = await self.ask_llm(prompt, max_tokens=2000)
        out = Path(f"workspace/ui/components/{name}.tsx")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
        return self.ok(component=name, path=str(out))

    async def _critique(self, code: str) -> dict:
        """Review existing UI code and suggest improvements."""
        prompt = f"""{UI_DESIGN_PROMPT}

Review this UI code and provide specific improvements:

```tsx
{code[:3000]}
```

Analyze:
1. Visual hierarchy issues
2. Spacing inconsistencies
3. Color/contrast problems
4. Missing states (loading, error, empty)
5. Accessibility gaps
6. Mobile responsiveness
7. Dark mode gaps

For each issue, provide the FIXED code snippet."""

        critique = await self.ask_llm(prompt, max_tokens=2000)
        return self.ok(critique=critique)

    async def _color_palette(self, brand: str) -> dict:
        """Generate a complete Tailwind color palette for a brand."""
        prompt = f"""Generate a complete Tailwind CSS color configuration for brand: "{brand}"

Output a tailwind.config.ts colors section with:
- primary (5 shades: 50, 100, 300, 500, 700, 900)
- secondary
- accent
- semantic: success, warning, danger, info

Also provide the CSS variables for dark mode in globals.css format.

Return as JSON: {{"tailwind_colors": {{}}, "css_variables": "..."}}"""

        response = await self.ask_llm(prompt, max_tokens=1500)
        return self.ok(brand=brand, palette=response)

    async def _generate_ui(self, description: str) -> dict:
        """Generic UI generation from description."""
        prompt = f"""{UI_DESIGN_PROMPT}

Generate a beautiful, complete UI for: "{description}"

Return production-ready TSX code with:
- Proper layout
- shadcn/ui components
- TailwindCSS styling
- TypeScript
- Realistic content"""

        code = await self.ask_llm(prompt, max_tokens=3000)
        slug = description[:30].replace(" ", "_").lower()
        out = Path(f"workspace/ui/{slug}.tsx")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code)
        return self.ok(path=str(out), lines=len(code.splitlines()))
