import sys, time
sys.path.insert(0, r'C:\Users\alexa\Downloads\AI Operations Command Center')
from dotenv import load_dotenv
load_dotenv()
from runner.main import run_cycle
print('Runner started', flush=True)
while True:
    try:
        run_cycle()
    except Exception as e:
        print(f'Cycle error: {e}', flush=True)
    time.sleep(120)
