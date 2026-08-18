import requests, json, time

questions = [
    'Bu döküman ne anlatıyor?',
    'Adaydan ne yetenekler bekleniyor?',
    'Proje kapsamında neler yapılacak?',
    'Teslim süresi ne kadar?'
]

for q in questions:
    start = time.time()
    body = {'question': q, 'top_k': 3, 'selected_docs': []}
    r = requests.post('http://localhost:8000/api/query', json=body, timeout=120)
    elapsed = round(time.time() - start, 2)
    resp = r.json()
    print(f'Soru: {q}')
    print(f'Sure: {elapsed}s')
    print(f'Cevap: {resp.get("answer", "")}')
    print(f'Kaynak: {resp.get("sources", [])}')
    print('-' * 60)
