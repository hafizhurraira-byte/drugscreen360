try:
    import pandas
except Exception:
    raise SystemExit(2)

print(pandas.__version__)