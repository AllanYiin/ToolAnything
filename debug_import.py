import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

try:
    from toolanything.core.models import ToolDefinition
    print("ToolDefinition imported successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
