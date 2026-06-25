import importlib.util
import pkgutil

def find_loader(fullname):
    try:
        spec = importlib.util.find_spec(fullname)
        if spec is not None:
            return spec.loader
    except Exception:
        pass
    return None

pkgutil.find_loader = find_loader

from dash_app import app
from layouts import serve_layout
import callbacks

app.layout = serve_layout()

if __name__ == '__main__':
    app.run(debug=True, dev_tools_ui=False, port=8051)

