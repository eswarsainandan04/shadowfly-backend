from multiprocessing import Process
import os

flask_apps = {
    "admin.py": 5000,
    "admins.py": 5072,
    "assign.py": 5008,
    "delivery.py": 5042,
    "drones.py": 5014,
    "home.py": 5080,
    "packagemanagement.py": 5024,
    "warehouse_details.py": 5028,
    "users.py": 5062,
    "drone_operating.py": 5090,
    "drone_monitering.py": 5095,
}

def run_app(filename, port):
    # Modify this if you're using Flask CLI or different entrypoints
    os.system(f'python {filename} --port={port}')

if __name__ == '__main__':
    processes = []
    for file, port in flask_apps.items():
        p = Process(target=run_app, args=(file, port))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
