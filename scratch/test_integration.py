import sys
import os

# Set dummy environment token for loading telebot without crashing
os.environ['BOT_TOKEN'] = '123456:dummy_token'

# Add parent directory to path to locate kalich
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import kalich

def run_integration_test():
    print("Testing parse_date_range:")
    start, end = kalich.parse_date_range("15.06.2026 - 19.06.2026")
    print(f"Parsed: {start} to {end}")
    assert start == '2026-06-15'
    assert end == '2026-06-19'
    
    print("\nTesting generate_group_subject_chart (group 50, department 1):")
    buf = kalich.generate_group_subject_chart(50, 1, "Бух-41", start, end)
    if buf:
        print("Success! Generated subject chart buffer.")
        with open("scratch/integration_subject_chart.png", "wb") as f:
            f.write(buf.getbuffer())
    else:
        print("No subject data found for this group.")

    print("\nTesting generate_group_daily_chart (group 50, department 1):")
    buf = kalich.generate_group_daily_chart(50, 1, "Бух-41", start, end)
    if buf:
        print("Success! Generated daily chart buffer.")
        with open("scratch/integration_daily_chart.png", "wb") as f:
            f.write(buf.getbuffer())
    else:
        print("No daily data found for this group.")

    print("\nTesting generate_time_distribution_chart:")
    buf = kalich.generate_time_distribution_chart(1, start, end)
    if buf:
        print("Success! Generated time slots chart buffer.")
        with open("scratch/integration_time_chart.png", "wb") as f:
            f.write(buf.getbuffer())
    else:
        print("No time slot data found.")

    print("\nTesting generate_teacher_groups_chart (rooms=['203'], department=1):")
    buf = kalich.generate_teacher_groups_chart("Тест Учитель", ["203"], 1, start, end)
    if buf:
        print("Success! Generated teacher groups chart buffer.")
        with open("scratch/integration_teacher_groups_chart.png", "wb") as f:
            f.write(buf.getbuffer())
    else:
        print("No teacher data found.")

    print("\nAll integration tests passed successfully!")

if __name__ == '__main__':
    run_integration_test()
