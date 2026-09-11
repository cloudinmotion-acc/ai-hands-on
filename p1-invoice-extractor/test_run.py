from reader import file_to_images
from extractor import extract

images = file_to_images(r"C:\Users\aaleti.bharath\OneDrive - Accenture\Desktop\Random\main-proj\ai-hands-on\p1-invoice-extractor\invoices\invoices-poc1.pdf")
print(f"pages loaded: {len(images)}")

result = extract(images)
print(result.model_dump_json(indent=2))