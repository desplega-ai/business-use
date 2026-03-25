"""
File with no business-use imports.
Scanner should skip this file entirely (quick exit).
"""
from flask import Flask

app = Flask(__name__)


@app.route("/health")
def health():
    return {"status": "ok"}


# This function happens to be called "ensure" but it's NOT from business_use
def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


ensure(True, "This should not be extracted")
