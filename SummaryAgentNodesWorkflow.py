"""
SummaryAgentNodesWorkflow - Orchestrates the trading summary workflow
"""
import json
import logging
from State import State
from SummaryAgentNodes import SummaryAgent, MT5Connection

logger = logging.getLogger(__name__)


class SummaryAgentNodesWorkflow:
    """Workflow orchestrator for the trading summary process"""

    def __init__(self, settings_file='settings.json', settings_override=None):
        """
        Initialize the workflow
        :param settings_file: Path to the settings JSON file
        :param settings_override: Optional dict to override loaded settings
        """
        self.settings_file = settings_file
        if settings_override is not None:
            self.settings = settings_override
            logger.info("Settings loaded from override")
        else:
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
            logger.info(f"Settings loaded from {self.settings_file}")
            return settings
        except FileNotFoundError:
            logger.error(f"Settings file '{self.settings_file}' not found")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in settings file: {e}")
            raise
            
    def run(self):
        """
        Execute the complete workflow with proper error handling
        :return: Final state object
        """
        logger.info("="*60)
        logger.info("Starting Trading Summary Workflow")
        logger.info("="*60)
        
        # Initialize state
        self.state = State()
        
        try:
            # Use context manager for MT5 connection lifecycle
            with MT5Connection(self.agent, self.state):
                
                if not self.state.mt5_connected or not self.state.logged_in:
                    logger.error("Failed to initialize and login to MT5. Aborting workflow.")
                    return self.state
                logger.info("[OK] MT5 initialized and logged in")
                
                # Step 2: Generate daily summary
                logger.info("Generating daily summary...")
                self.state = self.agent.summarize_day(self.state)
                logger.info("[OK] Daily summary complete")
                
                # Step 3: Generate weekly summary
                logger.info("Generating weekly summary...")
                self.state = self.agent.summarize_week(self.state)
                logger.info("[OK] Weekly summary complete")
                
                # Step 4: Generate monthly summary
                logger.info("Generating monthly summary...")
                self.state = self.agent.summarize_month(self.state)
                logger.info("[OK] Monthly summary complete")
                
                # Step 5: Generate yearly summary
                logger.info("Generating yearly summary...")
                self.state = self.agent.summarize_year(self.state)
                logger.info("[OK] Yearly summary complete")
                
                # Step 6: Analyze with LLM
                logger.info("Analyzing trading performance with AI...")
                self.state = self.agent.analyze_with_llm(self.state)
                logger.info("[OK] AI analysis complete")
                
                # Step 7: Send summaries to Telegram
                logger.info("Sending summaries to Telegram...")
                self.state = self.agent.send_telegram_summary(self.state)
                
                if self.state.telegram_sent:
                    logger.info("[OK] Summaries sent to Telegram")
                else:
                    logger.warning("[WARN] Failed to send to Telegram")
            
            # MT5 connection automatically closed by context manager
            logger.info("="*60)
            logger.info("Workflow Complete!")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Error during workflow execution: {e}", exc_info=True)
            self.state.add_error(str(e))
                
        return self.state
        
    def run_quick_summary(self, period='day'):
        """
        Run a quick summary for a specific period only
        :param period: 'day', 'week', 'month', or 'year'
        :return: Summary dictionary
        """
        self.state = State()
        
        try:
            with MT5Connection(self.agent, self.state):
                if not self.state.mt5_connected or not self.state.logged_in:
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
                    logger.error(f"Invalid period: {period}")
                    summary = None
                
                return summary
            
        except Exception as e:
            logger.error(f"Error in quick summary: {e}", exc_info=True)
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
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('trading_summary.log'),
            logging.StreamHandler()
        ]
    )
    
    # Create and run the workflow
    workflow = SummaryAgentNodesWorkflow()
    final_state = workflow.run()
    
    # Print final state report
    print("\n" + final_state.get_summary_report())