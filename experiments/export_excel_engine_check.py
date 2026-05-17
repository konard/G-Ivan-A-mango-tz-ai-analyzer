from io import BytesIO
import pandas as pd

buf = BytesIO()
pd.DataFrame({"a": ["тест"]}).to_excel(buf, index=False)
print(len(buf.getvalue()))
