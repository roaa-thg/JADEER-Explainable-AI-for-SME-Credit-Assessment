import threading, time, urllib.request

def ping():
    while True:
        try:
            urllib.request.urlopen(
                "https://jadeer-explainable-ai-for-sme-credit-assessment-26pmyppk5cvlyz.streamlit.app/"
            )
        except:
            pass
        time.sleep(300)  # كل 5 دقائق

t = threading.Thread(target=ping, daemon=True)
t.start()
