from platform_core.repository import Repository
import json

try:
    repo = Repository()
    doc = repo.load()
    print("Successfully loaded doc.")
    print("Rooms:", list(doc.get("rooms", {}).keys()))
except Exception as e:
    import traceback
    traceback.print_exc()
