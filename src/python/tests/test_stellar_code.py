
import stellar_code.stellar_code as stellar_code

def sample_data():
    return [
            {'name':'Sol', 'ra':0, 'dec':0, 'dist':0, 'code': 'FFFXXXXXXXXX+XXX'},
            {'name':'Proxima Centauri', 'ra':14.495985, 'dec':-62.679485, 'dist':1.2959, 'code': 'GFF2XX2XX2XX+2XW'}
        ]

def test_encode_equitorial():
    for s in sample_data():
        code = stellar_code.encode_equitorial(s['ra'], s['dec'], s['dist'])
        assert code == s['code']
