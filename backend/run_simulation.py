import os
import sys

# Ensure app package is importable
sys.path.insert(0, os.path.dirname(__file__))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.services.simulation import TimeMachineSimulation

if __name__ == "__main__":
    print("==================================================")
    print("CASHLOOP CLOSED-LOOP TIME MACHINE SIMULATION")
    print("==================================================")
    sim = TimeMachineSimulation()
    sim.run()
