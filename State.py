"""
State - Manages the state information for the trading summary workflow
"""
from datetime import datetime


class State:
    """State class to track workflow execution and data"""
    
    def __init__(self):
        """Initialize the state with default values"""
        self.timestamp = datetime.now()
        self.mt5_connected = False
        self.logged_in = False
        self.daily_summary = None
        self.weekly_summary = None
        self.monthly_summary = None
        self.yearly_summary = None
        self.llm_analysis = None
        self.telegram_sent = False
        self.messages = []
        self.errors = []
        
    def add_message(self, message):
        """
        Add a message to the state
        :param message: Message string to add
        """
        self.messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def add_error(self, error):
        """
        Add an error to the state
        :param error: Error string to add
        """
        self.errors.append(f"[{datetime.now().strftime('%H:%M:%S')}] {error}")
        
    def is_ready_for_summary(self):
        """
        Check if state is ready to generate summaries
        :return: Boolean indicating if ready
        """
        return self.mt5_connected and self.logged_in
        
    def has_summaries(self):
        """
        Check if any summaries have been generated
        :return: Boolean indicating if summaries exist
        """
        return any([
            self.daily_summary is not None,
            self.weekly_summary is not None,
            self.monthly_summary is not None,
            self.yearly_summary is not None
        ])
        
    def reset(self):
        """Reset the state for a new workflow run"""
        self.timestamp = datetime.now()
        self.mt5_connected = False
        self.logged_in = False
        self.daily_summary = None
        self.weekly_summary = None
        self.monthly_summary = None
        self.yearly_summary = None
        self.llm_analysis = None
        self.telegram_sent = False
        self.messages = []
        self.errors = []
        
    def get_summary_report(self):
        """
        Get a formatted summary report of the current state
        :return: String with formatted report
        """
        report = f"\n{'='*50}\n"
        report += f"State Report - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"{'='*50}\n"
        report += f"MT5 Connected: {self.mt5_connected}\n"
        report += f"Logged In: {self.logged_in}\n"
        report += f"Telegram Sent: {self.telegram_sent}\n"
        report += f"\nSummaries Generated:\n"
        report += f"  - Daily: {'✓' if self.daily_summary else '✗'}\n"
        report += f"  - Weekly: {'✓' if self.weekly_summary else '✗'}\n"
        report += f"  - Monthly: {'✓' if self.monthly_summary else '✗'}\n"
        report += f"  - Yearly: {'✓' if self.yearly_summary else '✗'}\n"
        report += f"  - LLM Analysis: {'✓' if self.llm_analysis else '✗'}\n"
        
        if self.messages:
            report += f"\nMessages ({len(self.messages)}):\n"
            for msg in self.messages[-5:]:  # Show last 5 messages
                report += f"  {msg}\n"
                
        if self.errors:
            report += f"\nErrors ({len(self.errors)}):\n"
            for err in self.errors:
                report += f"  {err}\n"
                
        report += f"{'='*50}\n"
        return report
        
    def __repr__(self):
        """String representation of the state"""
        return f"State(connected={self.mt5_connected}, logged_in={self.logged_in}, summaries={self.has_summaries()})"
