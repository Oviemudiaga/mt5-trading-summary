"""
Main entry point for the MT5 Trading Summary application
Runs the workflow on a scheduled basis (hourly checks)
"""
import time
import json
from datetime import datetime
from SummaryAgentNodesWorkflow import SummaryAgentNodesWorkflow


def load_settings(settings_file='settings.json'):
    """
    Load settings from JSON file
    :param settings_file: Path to settings file
    :return: Settings dictionary
    """
    try:
        with open(settings_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading settings: {e}")
        return None


def should_run_workflow(settings, last_run_time):
    """
    Check if the workflow should run
    - Weekdays (Mon-Fri): Every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)
    - Weekends (Sat-Sun): Once per day at 23:00
    :param settings: Settings dictionary
    :param last_run_time: DateTime of last run
    :return: Boolean indicating if workflow should run
    """
    now = datetime.now()
    current_minute = now.minute
    current_hour = now.hour
    current_weekday = now.weekday()  # 0=Monday, 6=Sunday

    # Only run on the hour (when minute is 0)
    if current_minute != 0:
        return False

    # Prevent duplicate runs (must be at least 1 hour since last run)
    if last_run_time is not None and (now - last_run_time).total_seconds() < 3600:
        return False

    # Weekend (Saturday=5, Sunday=6): Run once at 23:00
    if current_weekday >= 5:
        if current_hour == 23:
            return True
        else:
            return False

    # Weekday (Monday-Friday): Run every 4 hours
    if current_hour in [0, 4, 8, 12, 16, 20]:
        return True
    return False


def run_scheduled_workflow():
    """
    Main scheduler loop - runs workflow every hour on the hour
    """
    print("="*70)
    print(" MT5 Trading Summary - Hourly Scheduler")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Load settings
    settings = load_settings()
    if not settings:
        print("❌ Failed to load settings. Exiting.")
        return
    
    print(f"🕐 Schedule:")
    print(f"   📅 Weekdays (Mon-Fri): Every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)")
    print(f"   📅 Weekends (Sat-Sun): Once per day at 23:00 (end of day)")
    print("Checking every minute...\n")
    
    last_run_time = None
    
    try:
        while True:
            now = datetime.now()
            current_time_str = now.strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if it's time to run (every hour on the hour)
            if should_run_workflow(settings, last_run_time):
                print(f"\n{'='*70}")
                print(f"⏰ Hourly trigger: {current_time_str}")
                print(f"{'='*70}\n")
                
                # Run the workflow
                try:
                    workflow = SummaryAgentNodesWorkflow()
                    final_state = workflow.run()
                    
                    # Print summary
                    print("\n" + final_state.get_summary_report())
                    
                    # Update last run time
                    last_run_time = now
                    
                    print(f"\n✓ Workflow completed at {datetime.now().strftime('%H:%M:%S')}")
                    next_hour = (now.hour + 1) % 24
                    print(f"Next run scheduled at {next_hour:02d}:00\n")
                    
                except Exception as e:
                    print(f"❌ Error running workflow: {e}")
                    print("Will retry at next hour.\n")
            
            # Sleep for 1 minute before next check
            time.sleep(60)
            
            # Print heartbeat every 15 minutes
            if now.minute % 15 == 0:
                next_hour = (now.hour + 1) % 24
                print(f"[{current_time_str}] Scheduler active... Next run: {next_hour:02d}:00")
                
    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("Scheduler stopped by user")
        print("="*70)
    except Exception as e:
        print(f"\n❌ Unexpected error in scheduler: {e}")


def run_workflow_now():
    """
    Run the workflow immediately (for testing or manual execution)
    """
    print("Running workflow immediately...\n")
    
    try:
        workflow = SummaryAgentNodesWorkflow()
        final_state = workflow.run()
        
        # Print summary
        print("\n" + final_state.get_summary_report())
        
        print("\n✓ Manual workflow execution completed")
        
    except Exception as e:
        print(f"❌ Error running workflow: {e}")


def main():
    """
    Main entry point - choose between scheduled or immediate execution
    """
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--now':
        # Run immediately
        run_workflow_now()
    elif len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("MT5 Trading Summary Application")
        print("\nUsage:")
        print("  python main.py          - Run scheduler (checks hourly)")
        print("  python main.py --now    - Run workflow immediately")
        print("  python main.py --help   - Show this help message")
        print("\nConfiguration:")
        print("  Edit settings.json to configure MT5 credentials, Telegram,")
        print("  and scheduled run time.")
    else:
        # Run scheduler
        run_scheduled_workflow()


if __name__ == "__main__":
    main()
