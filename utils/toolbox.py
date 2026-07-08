class ToolBox:
    def __init__(self):
        self.tools = {}

    def register(self, name, func):
        self.tools[name] = func

    def run(self, name, *args, **kwargs):
        if name in self.tools:
            return self.tools[name](*args, **kwargs)
        return "Tool not found"

    def create_tool(self, name, description):
        code = f"""
def {name}():
    return \"Auto-created tool: {description}\"
"""
        exec(code, globals())
        self.tools[name] = globals()[name]
        return f"Tool {name} created"
