import requests, json, time

pdf_path = r'C:\Users\MONSTER\Desktop\tusaş\tusas-doc-qa\test_doc\Case_Study_TUSAş_LLM.pdf'
img_path = r'C:\Users\MONSTER\Desktop\tusaş\tusas-doc-qa\test_doc\testocr.png'

# Upload PDF
with open(pdf_path, 'rb') as f:
    files = {'file': ('Case_Study_TUSAş_LLM.pdf', f, 'application/pdf')}
    r = requests.post('http://localhost:8000/api/documents/upload', files=files)
pdf_data = r.json()
print('PDF yukleme:', pdf_data.get('status'), '-', pdf_data.get('duration'), 'saniye')

# Upload image
with open(img_path, 'rb') as f:
    files = {'file': ('testocr.png', f, 'image/png')}
    r = requests.post('http://localhost:8000/api/documents/upload', files=files)
img_data = r.json()
print('Resim yukleme:', img_data.get('status'), '-', img_data.get('duration'), 'saniye')

question = 'Bu döküman ne anlatıyor?'
print('\nSoru:', question)
print('-' * 60)

# Query only PDF
start = time.time()
body = {'question': question, 'top_k': 3, 'selected_docs': ['Case_Study_TUSAş_LLM.pdf']}
r = requests.post('http://localhost:8000/api/query', json=body, timeout=120)
pdf_elapsed = round(time.time() - start, 2)
pdf_resp = r.json()
print('PDF sorusu:', pdf_elapsed, 'saniye')
print('Cevap:', pdf_resp.get('answer', '')[:400])

print('-' * 60)

# Query only image
start = time.time()
body = {'question': question, 'top_k': 3, 'selected_docs': ['testocr.png']}
r = requests.post('http://localhost:8000/api/query', json=body, timeout=120)
img_elapsed = round(time.time() - start, 2)
img_resp = r.json()
print('Resim sorusu:', img_elapsed, 'saniye')
print('Cevap:', img_resp.get('answer', '')[:400])

print('\n--- Karsilastirma ---')
print('PDF sure:', pdf_elapsed, 'saniye')
print('Resim sure:', img_elapsed, 'saniye')
print('Fark:', abs(pdf_elapsed - img_elapsed), 'saniye')
