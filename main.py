"""
Main entry point for the MT5 Trading Summary application
Runs the workflow on a scheduled basis (hourly checks)
"""
import time
import json
import logging
import sys
from datetime import datetime, timedelta
from SummaryAgentNodesWorkflow import SummaryAgentNodesWorkflow


# Setup logging
def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('trading_summary.log'),
            logging.StreamHandler()
        ]
    )


logger = logging.getLogger(__name__)


def load_settings(settings_file='settings.json'):
    """
    Load settings from JSON file
    :param settings_file: Path to settings file
    :return: Settings dictionary
    """
    try:
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        logger.info(f"Settings loaded from {settings_file}")
        return settings
    except FileNotFoundError:
        logger.error(f"Settings file '{settings_file}' not found. Please create it from settings.example.json")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in settings file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return None


def validate_settings(settings):
    """
    Validate that all required settings are present
    :param settings: Settings dictionary
    :return: Boolean indicating if settings are valid
    """
    if not settings:
        return False
        
    # Check for accounts
    if 'accounts' not in settings or not settings['accounts']:
        logger.error("No accounts configured in settings")
        return False
    
    # Validate each account
    required_account_keys = ['server', 'username', 'password', 'mt5_pathway']
    for idx, account in enumerate(settings['accounts']):
        for key in required_account_keys:
            if key not in account or not account[key]:
                logger.error(f"Account {idx+1} missing required field: {key}")
                return False
    
    logger.info("Settings validation passed")
    return True


def should_run_workflow(settings, last_run_time):
    """
    Check if the workflow should run
    - Weekdays: every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)
    - Weekends: once a day (12:00)
    :param settings: Settings dictionary
    :param last_run_time: DateTime of last run
    :return: Boolean indicating if workflow should run
    """
    now = datetime.now()
    
    # Allow runs within the first 2 minutes of the hour to account for timing
    if now.minute >= 2:
        return False
    
    # Prevent duplicate runs (must be at least 3 hours 50 minutes since last run)
    if last_run_time is not None and (now - last_run_time).total_seconds() < 13800:  # 3.5 hours
        return False
    
    # Weekends: run once a day at 12:00
    if now.weekday() >= 5:  # 5=Saturday, 6=Sunday
        if now.hour != 12:
            return False
    else:
        # Weekdays: run every 4 hours
        if now.hour % 4 != 0:
            return False
    
    return True


def calculate_sleep_time():
    """
    Calculate seconds until the next scheduled run
    - Weekdays: every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)
    - Weekends: once a day (12:00)
    :return: Number of seconds to sleep
    """
    now = datetime.now()
    
    # If it's weekend
    if now.weekday() >= 5:  # Saturday or Sunday
        # Calculate time until next 12:00
        if now.hour < 12:
            # Today at 12:00
            next_run = now.replace(hour=12, minute=0, second=0, microsecond=0)
        else:
            # Tomorrow at 12:00
            next_run = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    else:
        # Weekday: calculate next 4-hour interval
        current_hour = now.hour
        # Find next 4-hour mark: 0, 4, 8, 12, 16, 20
        next_hour = ((current_hour // 4) + 1) * 4
        
        if next_hour >= 24:
            # Move to next day
            next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_run = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
    
    sleep_seconds = (next_run - now).total_seconds()
    
    # Minimum sleep of 30 seconds, maximum of calculated time
    return max(30, min(sleep_seconds, sleep_seconds))


def run_scheduled_workflow():
    """
    Main scheduler loop - runs workflow every 2 minutes
    """
    print("="*70)
    print(" MT5 Trading Summary - Smart Scheduler")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Load settings
    settings = load_settings()
    if not settings:
        logger.error("Failed to load settings. Exiting.")
        print("❌ Failed to load settings. Exiting.")
        return
    
    # Validate settings
    if not validate_settings(settings):
        logger.error("Settings validation failed. Exiting.")
        print("❌ Settings validation failed. Exiting.")
        return
    
    print(f"🕐 Schedule: Weekdays every 4 hours (00:00, 04:00, 08:00, 12:00, 16:00, 20:00), Weekends daily at 12:00")
    print("Smart sleep mode enabled (wakes up at scheduled times)\n")
    
    last_run_time = None

    try:
        while True:
            now = datetime.now()
            current_time_str = now.strftime('%Y-%m-%d %H:%M:%S')

            # Check if it's time to run (weekdays every 4 hours, weekends daily at 12:00)
            if should_run_workflow(settings, last_run_time):
                schedule_type = "weekend daily" if now.weekday() >= 5 else "weekday 4-hour"
                logger.info(f"{schedule_type.capitalize()} trigger: {current_time_str}")
                print(f"\n{'='*70}")
                print(f"⏰ {schedule_type.capitalize()} trigger: {current_time_str}")
                print(f"{'='*70}\n")

                accounts = settings.get('accounts', [])
                for idx, account_cfg in enumerate(accounts):
                    account_name = account_cfg.get('username', 'N/A')
                    server_name = account_cfg.get('server', 'N/A')
                    
                    logger.info(f"Processing account {idx+1}/{len(accounts)}: {account_name} @ {server_name}")
                    print(f"\n{'='*60}\nAccount {idx+1}/{len(accounts)}: {account_name} @ {server_name}\n{'='*60}")
                    
                    try:
                        # Merge global settings with account settings for workflow
                        account_settings = dict(settings)
                        account_settings.update(account_cfg)
                        workflow = SummaryAgentNodesWorkflow(settings_override=account_settings)
                        final_state = workflow.run()
                        print("\n" + final_state.get_summary_report())
                        logger.info(f"Workflow execution for account {account_name} completed")
                        print("\n✓ Workflow execution for account completed\n")
                    except Exception as e:
                        logger.error(f"Error running workflow for account {account_name}: {e}", exc_info=True)
                        print(f"❌ Error running workflow for account: {e}")
                
                # Update last run time after all accounts processed
                last_run_time = now
                completion_time = datetime.now().strftime('%H:%M:%S')
                logger.info(f"Workflow completed at {completion_time}")
                print(f"\n✓ All workflows completed at {completion_time}")
                
                # Calculate next run time based on schedule
                if now.weekday() >= 5:  # Weekend
                    next_run_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
                    if now.hour >= 12:  # After 12:00, next run is tomorrow
                        next_run_time += timedelta(days=1)
                    schedule_desc = "weekends daily"
                else:  # Weekday
                    hours_to_next = 4 - (now.hour % 4)
                    if hours_to_next == 4:
                        hours_to_next = 0
                    next_run_time = now.replace(hour=now.hour + hours_to_next, minute=0, second=0, microsecond=0)
                    # If next run would be on weekend, adjust to weekend schedule
                    if next_run_time.weekday() >= 5:
                        next_run_time = next_run_time.replace(hour=12, minute=0, second=0, microsecond=0)
                        days_to_add = (5 - next_run_time.weekday()) % 7  # To Saturday
                        if days_to_add == 0 and next_run_time.hour >= 12:
                            days_to_add = 2  # Saturday after 12:00, wait for Sunday
                        elif days_to_add == 0:
                            pass  # Saturday before 12:00, keep as is
                        next_run_time += timedelta(days=days_to_add)
                    schedule_desc = "weekdays 4-hour"
                
                print(f"Next run scheduled at {next_run_time.strftime('%Y-%m-%d %H:%M:%S')} ({schedule_desc})\n")

            # Smart sleep - calculate time until next even minute
            sleep_time = calculate_sleep_time()
            logger.debug(f"Sleeping for {sleep_time:.0f} seconds until next check")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        print("\n\n" + "="*70)
        print("Scheduler stopped by user")
        print("="*70)
    except Exception as e:
        logger.error(f"Unexpected error in scheduler: {e}", exc_info=True)
        print(f"\n❌ Unexpected error in scheduler: {e}")


def run_workflow_now():
    """
    Run the workflow immediately (for testing or manual execution)
    """
    print("Running workflow immediately...\n")
    logger.info("Running workflow immediately (manual execution)")

    settings = load_settings()
    if not settings:
        print("❌ Failed to load settings. Exiting.")
        return
    
    if not validate_settings(settings):
        print("❌ Settings validation failed. Exiting.")
        return

    accounts = settings.get('accounts', [])
    for idx, account_cfg in enumerate(accounts):
        account_name = account_cfg.get('username', 'N/A')
        server_name = account_cfg.get('server', 'N/A')
        
        logger.info(f"Processing account {idx+1}/{len(accounts)}: {account_name} @ {server_name}")
        print(f"\n{'='*60}\nAccount {idx+1}/{len(accounts)}: {account_name} @ {server_name}\n{'='*60}")
        
        try:
            # Merge global settings with account settings for workflow
            account_settings = dict(settings)
            account_settings.update(account_cfg)
            workflow = SummaryAgentNodesWorkflow(settings_override=account_settings)
            final_state = workflow.run()
            print("\n" + final_state.get_summary_report())
            logger.info(f"Workflow execution for account {account_name} completed")
            print("\n✓ Workflow execution for account completed\n")
        except Exception as e:
            logger.error(f"Error running workflow for account {account_name}: {e}", exc_info=True)
            print(f"❌ Error running workflow for account: {e}")


def validate_connection():
    """
    Validate MT5 connectivity without running the full workflow
    """
    print("Validating MT5 connection...\n")
    logger.info("Running connection validation")
    
    settings = load_settings()
    if not settings:
        print("❌ Failed to load settings. Exiting.")
        return
    
    if not validate_settings(settings):
        print("❌ Settings validation failed. Exiting.")
        return
    
    accounts = settings.get('accounts', [])
    all_success = True
    
    for idx, account_cfg in enumerate(accounts):
        account_name = account_cfg.get('username', 'N/A')
        server_name = account_cfg.get('server', 'N/A')
        
        print(f"\n{'='*60}")
        print(f"Testing Account {idx+1}/{len(accounts)}: {account_name} @ {server_name}")
        print(f"{'='*60}")
        
        try:
            from State import State
            from SummaryAgentNodes import SummaryAgent
            
            agent = SummaryAgent(account_cfg)
            state = State()
            
            # Try to connect
            state = agent.initialize_mt5(state)
            
            if state.mt5_connected and state.logged_in:
                print(f"✓ Successfully connected to {server_name}")
                print(f"✓ Account {account_name} validated")
                
                # Get account info
                account_info = agent.get_account_info()
                if account_info:
                    print(f"  Balance: ${account_info['balance']:.2f}")
                    print(f"  Equity: ${account_info['equity']:.2f}")
                    print(f"  Free Margin: ${account_info['free_margin']:.2f}")
                
                # Cleanup
                agent.shutdown_mt5(state)
                print("✓ Connection closed cleanly\n")
            else:
                print(f"❌ Failed to connect to {server_name}")
                all_success = False
                
        except Exception as e:
            logger.error(f"Error validating account {account_name}: {e}", exc_info=True)
            print(f"❌ Error: {e}\n")
            all_success = False
    
    print("="*60)
    if all_success:
        print("✓ All accounts validated successfully")
        logger.info("Connection validation successful")
    else:
        print("⚠ Some accounts failed validation")
        logger.warning("Connection validation completed with errors")
    print("="*60)


def main():
    """
    Main entry point - choose between scheduled or immediate execution
    """
    # Setup logging first
    setup_logging()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == '--now':
            # Run immediately
            run_workflow_now()
        elif command == '--validate':
            # Validate connection only
            validate_connection()
        elif command == '--help':
            print("MT5 Trading Summary Application")
            print("\nUsage:")
            print("  python main.py               - Run scheduler (weekdays: 4h intervals, weekends: daily)")
            print("  python main.py --now         - Run workflow immediately")
            print("  python main.py --validate    - Test MT5 connection without running workflow")
            print("  python main.py --help        - Show this help message")
            print("\nConfiguration:")
            print("  1. Copy settings.example.json to settings.json")
            print("  2. Edit settings.json with your MT5 credentials and Telegram settings")
            print("  3. Ensure Ollama is running if LLM analysis is enabled")
            print("\nLogs:")
            print("  Application logs are saved to trading_summary.log")
        else:
            print(f"Unknown command: {command}")
            print("Use --help to see available commands")
    else:
        # Run scheduler
        run_scheduled_workflow()


if __name__ == "__main__":
    main()