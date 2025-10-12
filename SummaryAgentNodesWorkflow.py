"""
SummaryAgentNodesWorkflow - Orchestrates the trading summary workflow
"""
import json
from State import State
from SummaryAgentNodes import SummaryAgent


class SummaryAgentNodesWorkflow:
    """Workflow orchestrator for the trading summary process"""
    
    def __init__(self, settings_file='settings.json'):
        """
        Initialize the workflow
        :param settings_file: Path to the settings JSON file
        """
        self.settings_file = settings_file
        self.settings = self.load_settings()
        self.agent = SummaryAgent(self.settings)
        self.state = None
        
    def load_settings(self):
        """
        Load settings from JSON file
        :return: Dictionary with settings
        """
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
            print(f"Settings loaded from {self.settings_file}")
            return settings
        except FileNotFoundError:
            print(f"Error: Settings file '{self.settings_file}' not found")
            raise
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in settings file: {e}")
            raise
            
    def run(self):
        """
        Execute the complete workflow
        :return: Final state object
        """
        print("\n" + "="*60)
        print("Starting Trading Summary Workflow")
        print("="*60 + "\n")
        
        # Initialize state
        self.state = State()
        
        try:
            # Step 1: Initialize MT5 connection and login
            print("Step 1: Initializing MT5 connection and logging in...")
            self.state = self.agent.initialize_mt5(self.state)
            
            if not self.state.mt5_connected or not self.state.logged_in:
                print("❌ Failed to initialize and login to MT5. Aborting workflow.")
                return self.state
            print("✓ MT5 initialized and logged in\n")
            
            # Step 2: Generate daily summary
            print("Step 2: Generating daily summary...")
            self.state = self.agent.summarize_day(self.state)
            print("✓ Daily summary complete\n")
            
            # Step 3: Generate weekly summary
            print("Step 3: Generating weekly summary...")
            self.state = self.agent.summarize_week(self.state)
            print("✓ Weekly summary complete\n")
            
            # Step 4: Generate monthly summary
            print("Step 4: Generating monthly summary...")
            self.state = self.agent.summarize_month(self.state)
            print("✓ Monthly summary complete\n")
            
            # Step 5: Generate yearly summary
            print("Step 5: Generating yearly summary...")
            self.state = self.agent.summarize_year(self.state)
            print("✓ Yearly summary complete\n")
            
            # Step 6: Analyze with LLM
            print("Step 6: Analyzing trading performance with AI...")
            self.state = self.agent.analyze_with_llm(self.state)
            print("✓ AI analysis complete\n")
            
            # Step 7: Send summaries to Telegram
            print("Step 7: Sending summaries to Telegram...")
            self.state = self.agent.send_telegram_summary(self.state)
            
            if self.state.telegram_sent:
                print("✓ Summaries sent to Telegram\n")
            else:
                print("⚠ Failed to send to Telegram\n")
            
            # Step 8: Shutdown MT5 connection
            print("Step 8: Shutting down MT5 connection...")
            self.state = self.agent.shutdown_mt5(self.state)
            print("✓ MT5 connection closed\n")
            
            print("="*60)
            print("Workflow Complete!")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ Error during workflow execution: {e}")
            self.state.add_error(str(e))
            
            # Ensure MT5 is shutdown even if there's an error
            if self.state.mt5_connected:
                print("Attempting to shutdown MT5 after error...")
                self.state = self.agent.shutdown_mt5(self.state)
                
        return self.state
        
    def run_quick_summary(self, period='day'):
        """
        Run a quick summary for a specific period only
        :param period: 'day', 'week', 'month', or 'year'
        :return: Summary dictionary
        """
        self.state = State()
        
        try:
            # Initialize and login
            self.state = self.agent.initialize_mt5(self.state)
            if not self.state.mt5_connected:
                return None
                
            self.state = self.agent.login_mt5(self.state)
            if not self.state.logged_in:
                self.agent.shutdown_mt5(self.state)
                return None
            
            # Get requested summary
            if period == 'day':
                self.state = self.agent.summarize_day(self.state)
                summary = self.state.daily_summary
            elif period == 'week':
                self.state = self.agent.summarize_week(self.state)
                summary = self.state.weekly_summary
            elif period == 'month':
                self.state = self.agent.summarize_month(self.state)
                summary = self.state.monthly_summary
            elif period == 'year':
                self.state = self.agent.summarize_year(self.state)
                summary = self.state.yearly_summary
            else:
                print(f"Invalid period: {period}")
                summary = None
            
            # Cleanup
            self.agent.shutdown_mt5(self.state)
            
            return summary
            
        except Exception as e:
            print(f"Error in quick summary: {e}")
            if self.state.mt5_connected:
                self.agent.shutdown_mt5(self.state)
            return None
            
    def get_state_report(self):
        """
        Get a formatted report of the current state
        :return: State report string
        """
        if self.state:
            return self.state.get_summary_report()
        else:
            return "No workflow has been run yet."


# Main execution for testing
if __name__ == "__main__":
    # Create and run the workflow
    workflow = SummaryAgentNodesWorkflow()
    final_state = workflow.run()
    
    # Print final state report
    print("\n" + final_state.get_summary_report())
