"""
Edge case test for mass times parsing.
"""
import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://maria.catholic.or.kr/'
}

def check_church(name, orgnum):
    print(f"\n=== {name} (orgnum={orgnum}) ===")
    
    # Check API data first
    r1 = requests.post(
        'https://catholicapi.catholic.or.kr/app/parish/getParishList.asp',
        data={'keyword': name[:3], 'app': 'goodnews', 'PAGE': 1, 'P_SIZE': 5},
        headers=headers
    )
    data = r1.json()
    for item in data.get('BOARDLIST', []):
        if str(item.get('orgnum')) == str(orgnum):
            print(f"API missatime: {item.get('missatime', 'NONE')}")
            break
    
    # Check detail page
    r2 = requests.get(
        f'https://maria.catholic.or.kr/mobile/church/bondang_view.asp?app=goodnews&orgnum={orgnum}',
        headers=headers
    )
    soup = BeautifulSoup(r2.content, 'html.parser')
    table = soup.select_one('table.register05')
    
    if table:
        print("Detail page table.register05 found:")
        for row in table.find_all('tr'):
            th = row.find('th')
            tds = row.find_all('td')
            th_text = th.get_text(strip=True) if th else ''
            td_texts = [td.get_text(strip=True) for td in tds]
            print(f"  th={th_text} | tds={td_texts}")
    else:
        print("No table.register05 found on detail page")

# Test cases
check_church("부안", 3609)
check_church("명동", 2115)
check_church("세종성요한", 4399)
