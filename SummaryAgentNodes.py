"""
SummaryAgent - A class for managing MetaTrader 5 connection and trade summaries
"""
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import requests
import ollama
import logging
import signal
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Custom timeout exception"""
    pass


@contextmanager
def timeout(seconds):
    """Context manager for timing out operations (cross-platform)"""
    def timeout_handler():
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Use signal-based timeout on Unix-like systems, threading on Windows
    if hasattr(signal, 'SIGALRM'):
        # Unix-like system
        original_handler = signal.signal(signal.SIGALRM, lambda signum, frame: timeout_handler())
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original_handler)
    else:
        # Windows or other systems without SIGALRM
        timer = threading.Timer(seconds, timeout_handler)
        timer.start()
        try:
            yield
        finally:
            timer.cancel()


class MT5Connection:
    """Context manager for MT5 connection lifecycle"""
    
    def __init__(self, agent, state):
        self.agent = agent
        self.state = state
        
    def __enter__(self):
        """Initialize MT5 connection"""
        self.state = self.agent.initialize_mt5(self.state)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure MT5 connection is properly closed"""
        if self.agent.connected or self.state.mt5_connected:
            try:
                mt5.shutdown()
                self.agent.connected = False
                self.agent.logged_in = False
                self.state.mt5_connected = False
                self.state.logged_in = False
                logger.info("MT5 connection closed (cleanup)")
            except Exception as e:
                logger.error(f"Error during MT5 cleanup: {e}")
        return False  # Don't suppress exceptions


class SummaryAgent:
    """Agent for connecting to MT5, retrieving trade history, and sending summaries"""
    
    def __init__(self, settings):
        """
        Initialize the SummaryAgent
        :param settings: Dictionary containing MT5 and Telegram settings
        """
        self.settings = settings
        self.connected = False
        self.logged_in = False
        self._validate_settings()
        
    def _validate_settings(self):
        """Validate required settings are present"""
        required_keys = ['username', 'password', 'server', 'mt5_pathway']
        for key in required_keys:
            if key not in self.settings:
                raise ValueError(f"Missing required setting: {key}")
        
        if self.settings.get('telegram', {}).get('enabled', False):
            telegram_keys = ['bot_token', 'chat_id']
            for key in telegram_keys:
                if key not in self.settings.get('telegram', {}):
                    raise ValueError(f"Missing required Telegram setting: {key}")
        
        logger.info("Settings validation passed")
        
    def initialize_mt5(self, state):
        """
        Initialize connection with the MetaTrader 5 terminal and login
        :param state: State object to track workflow
        :return: Updated state
        """
        try:
            # Get credentials
            mt5_pathway = self.settings['mt5_pathway']
            username = int(self.settings['username'])
            password = self.settings['password']
            server = self.settings['server']
            
            logger.info(f"Initializing MT5 connection to {server} with account {username}")
            
            # Attempt to initialize MT5 with login credentials
            # This establishes connection AND logs in at the same time
            mt5_init = mt5.initialize(
                path=mt5_pathway,
                login=username,
                password=password,
                server=server
            )
            
            if mt5_init:
                self.connected = True
                self.logged_in = True
                state.add_message(f"MT5 initialized and logged in successfully (Account: {username})")
                state.mt5_connected = True
                state.logged_in = True
                logger.info(f"MetaTrader5 package author: {mt5.__author__}")
                logger.info(f"MetaTrader5 package version: {mt5.__version__}")
                logger.info(f"Logged in to account: {username} on server: {server}")
            else:
                error_code = mt5.last_error()
                error_msg = f"MT5 initialization failed, error code: {error_code}"
                state.add_error(error_msg)
                state.mt5_connected = False
                state.logged_in = False
                
        except Exception as e:
            error_msg = f"Error initializing MetaTrader 5: {e}"
            state.add_error(error_msg)
            state.mt5_connected = False
            state.logged_in = False
            
        return state
    
    def get_trade_history(self, from_date, to_date):
        """
        Retrieve trade history from MT5
        :param from_date: Start date for history
        :param to_date: End date for history
        :return: List of deals or None if error
        """
        try:
            logger.debug(f"Querying deals from {from_date} to {to_date}")
            
            # Get deals in the specified time range
            deals = mt5.history_deals_get(from_date, to_date)
            
            if deals is None:
                error_code = mt5.last_error()
                logger.warning(f"No deals found, error code: {error_code}")
                return None
            elif len(deals) == 0:
                logger.info("No deals found in the specified time range")
                return []
            
            logger.info(f"Retrieved {len(deals)} deals")
            return list(deals)
            
        except Exception as e:
            logger.error(f"Error retrieving trade history: {e}")
            return None
        
    def get_open_positions(self):
        """
        Get currently open positions from MT5
        :return: List of open position dictionaries
        """
        try:
            positions = mt5.positions_get()
            
            if positions is None:
                error_code = mt5.last_error()
                logger.warning(f"No positions found, error code: {error_code}")
                return []
            
            if len(positions) == 0:
                return []
            
            # Format positions into readable dictionaries
            open_trades = []
            for pos in positions:
                trade = {
                    'symbol': pos.symbol,
                    'volume': pos.volume,
                    'open_price': pos.price_open,
                    'current_price': pos.price_current,
                    'profit': pos.profit,
                    'comment': pos.comment if hasattr(pos, 'comment') and pos.comment else 'No strategy'
                }
                open_trades.append(trade)
            
            logger.info(f"Retrieved {len(open_trades)} open positions")
            return open_trades
            
        except Exception as e:
            logger.error(f"Error retrieving open positions: {e}")
            return []
        

    def calculate_summary(self, deals):
            """
            Calculate summary statistics from deals
            :param deals: List of deals from MT5
            :return: Dictionary with summary statistics including strategy breakdown
            """
            if not deals:
                return {
                    'completed_trades': 0,
                    'total_pnl': 0.0,
                    'profit': 0.0,
                    'swap': 0.0,
                    'commission': 0.0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0.0,
                    'strategies': {}
                }

            # First pass: Build maps for round-trip analysis
            position_entries = {}
            position_exits = {}
            position_strategy_map = {}
            
            for deal in deals:
                if hasattr(deal, 'entry') and deal.entry == 0:  # Opening deal
                    comment = deal.comment if hasattr(deal, 'comment') else ''
                    if comment and comment.strip():
                        position_strategy_map[deal.position_id] = comment
                    position_entries[deal.position_id] = deal
                elif hasattr(deal, 'entry') and deal.entry == 1:  # Closing deal
                    position_exits[deal.position_id] = deal

            # Only count round-trips (positions with both entry and exit)
            round_trip_ids = set(position_entries.keys()) & set(position_exits.keys())
            strategies = {}
            total_profit = 0.0
            total_swap = 0.0
            total_commission = 0.0
            total_fee = 0.0
            winning_trades = 0
            losing_trades = 0
            completed_trades = 0
            
            for pos_id in round_trip_ids:
                entry_deal = position_entries[pos_id]
                exit_deal = position_exits[pos_id]
                profit = exit_deal.profit
                swap = exit_deal.swap if hasattr(exit_deal, 'swap') else 0.0
                commission = exit_deal.commission if hasattr(exit_deal, 'commission') else 0.0
                fee = exit_deal.fee if hasattr(exit_deal, 'fee') else 0.0
                comment = exit_deal.comment if hasattr(exit_deal, 'comment') else ''
                
                # Normalize comment and recover strategy from entry when appropriate
                comment_str = str(comment).strip() if comment is not None else ''
                
                # If exit comment is empty or only SL/TP markers, use the original entry comment
                if (not comment_str) and pos_id in position_strategy_map:
                    comment = position_strategy_map[pos_id]
                elif '[sl ' in comment_str.lower() or '[tp ' in comment_str.lower():
                    if pos_id in position_strategy_map:
                        comment = position_strategy_map[pos_id]
                else:
                    comment = comment_str
                
                # Categorize strategy with clear labels
                if 'CheckoutSC' in str(comment) or 'Checkout' in str(comment):
                    strategy = 'Deposit/Withdrawal'
                elif not comment or not str(comment).strip():
                    strategy = 'Untagged (Old Trades)'
                else:
                    strategy = comment
                
                # Initialize strategy if not exists
                if strategy not in strategies:
                    strategies[strategy] = {
                        'trades': 0,
                        'pnl': 0.0,
                        'wins': 0,
                        'losses': 0
                    }
                
                # Update strategy stats
                strategies[strategy]['trades'] += 1
                strategies[strategy]['pnl'] += profit + swap - commission - fee
                
                if profit > 0:
                    winning_trades += 1
                    strategies[strategy]['wins'] += 1
                elif profit < 0:
                    losing_trades += 1
                    strategies[strategy]['losses'] += 1
                
                total_profit += profit
                total_swap += swap
                total_commission += commission
                total_fee += fee
                completed_trades += 1

            # Calculate total P&L (profit + swap - commission - fee)
            total_pnl = total_profit + total_swap - total_commission - total_fee
            win_rate = (winning_trades / completed_trades * 100) if completed_trades > 0 else 0.0

            return {
                'completed_trades': completed_trades,
                'total_pnl': round(total_pnl, 2),
                'profit': round(total_profit, 2),
                'swap': round(total_swap, 2),
                'commission': round(total_commission, 2),
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': round(win_rate, 2),
                'strategies': strategies
            }
    
    def summarize_day(self, state):
        """
        Summarize trading results for the current day
        :param state: State object to track workflow
        :return: Updated state
        """
        if not state.logged_in:
            state.add_message("Cannot get daily summary - not logged in")
            return state
        
        try:
            # Get today's date range
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            now = datetime.now()
            
            deals = self.get_trade_history(today, now)
            summary = self.calculate_summary(deals)
            
            state.daily_summary = summary
            state.add_message(f"Daily summary: {summary['completed_trades']} trades, P&L: ${summary['total_pnl']}")
            logger.info(f"Daily Summary: Total P&L: ${summary['total_pnl']}, Trades: {summary['completed_trades']}")
            
            # Check for untagged trades (warning system)
            if 'Untagged (Old Trades)' in summary.get('strategies', {}):
                untagged_count = summary['strategies']['Untagged (Old Trades)']['trades']
                warning_msg = f"⚠️  WARNING: {untagged_count} untagged trade(s) detected today! Check your EA strategy tagging."
                logger.warning(warning_msg)
                state.add_message(f"WARNING: {untagged_count} untagged trades detected")
            
        except Exception as e:
            state.add_error(f"Error getting daily summary: {e}")
            
        return state
    
    def summarize_week(self, state):
        """
        Summarize trading results for the week to date
        :param state: State object to track workflow
        :return: Updated state
        """
        if not state.logged_in:
            state.add_message("Cannot get weekly summary - not logged in")
            return state
        
        try:
            # Get week start (Monday)
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            now = datetime.now()
            
            deals = self.get_trade_history(week_start, now)
            summary = self.calculate_summary(deals)
            
            state.weekly_summary = summary
            state.add_message(f"Weekly summary: {summary['completed_trades']} trades, P&L: ${summary['total_pnl']}")
            logger.info(f"Weekly Summary: Total P&L: ${summary['total_pnl']}, Trades: {summary['completed_trades']}")
            
        except Exception as e:
            state.add_error(f"Error getting weekly summary: {e}")
            
        return state
    
    def summarize_month(self, state):
        """
        Summarize trading results for the month to date
        :param state: State object to track workflow
        :return: Updated state
        """
        if not state.logged_in:
            state.add_message("Cannot get monthly summary - not logged in")
            return state
        
        try:
            # Get month start
            today = datetime.now()
            month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            now = datetime.now()
            
            deals = self.get_trade_history(month_start, now)
            summary = self.calculate_summary(deals)
            
            state.monthly_summary = summary
            state.add_message(f"Monthly summary: {summary['completed_trades']} trades, P&L: ${summary['total_pnl']}")
            logger.info(f"Monthly Summary: Total P&L: ${summary['total_pnl']}, Trades: {summary['completed_trades']}")
            
        except Exception as e:
            state.add_error(f"Error getting monthly summary: {e}")
            
        return state
    
    def summarize_year(self, state):
        """
        Summarize trading results for the year to date
        :param state: State object to track workflow
        :return: Updated state
        """
        if not state.logged_in:
            state.add_message("Cannot get yearly summary - not logged in")
            return state
        
        try:
            # Get year start
            today = datetime.now()
            year_start = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            now = datetime.now()
            
            deals = self.get_trade_history(year_start, now)
            summary = self.calculate_summary(deals)
            
            state.yearly_summary = summary
            state.add_message(f"Yearly summary: {summary['completed_trades']} trades, P&L: ${summary['total_pnl']}")
            logger.info(f"Yearly Summary: Total P&L: ${summary['total_pnl']}, Trades: {summary['completed_trades']}")
            
        except Exception as e:
            state.add_error(f"Error getting yearly summary: {e}")
            
        return state
    
    def shutdown_mt5(self, state):
        """
        Shutdown previously established connection to the MetaTrader 5 terminal
        :param state: State object to track workflow
        :return: Updated state
        """
        try:
            mt5.shutdown()
            self.connected = False
            self.logged_in = False
            state.mt5_connected = False
            state.logged_in = False
            state.add_message("MT5 connection shutdown successfully")
            logger.info("MT5 connection shutdown")
            
        except Exception as e:
            state.add_error(f"Error shutting down MT5: {e}")
            
        return state
    
    def send_telegram_summary(self, state):
        """
        Send all summaries to Telegram account with retry logic
        :param state: State object containing all summaries
        :return: Updated state
        """
        try:
            # Respect settings flag to enable/disable Telegram sending
            if not self.settings.get('telegram', {}).get('enabled', True):
                state.add_message('Telegram sending is disabled by settings')
                state.telegram_sent = False
                logger.info('Telegram sending is disabled by settings; skipping send')
                return state
                
            bot_token = self.settings['telegram']['bot_token']
            chat_id = self.settings['telegram']['chat_id']
            
            # Format the message
            message = self._format_summary_message(state)
            
            # Send via Telegram API with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    }
                    
                    response = requests.post(url, json=payload, timeout=10)
                    
                    if response.status_code == 200:
                        state.add_message("Summary sent to Telegram successfully")
                        state.telegram_sent = True
                        logger.info("Summary sent to Telegram successfully")
                        break
                    else:
                        error_msg = f"Failed to send Telegram message (attempt {attempt+1}/{max_retries}): {response.text}"
                        logger.warning(error_msg)
                        if attempt == max_retries - 1:
                            state.add_error(error_msg)
                            state.telegram_sent = False
                            
                except requests.exceptions.RequestException as e:
                    error_msg = f"Network error sending Telegram message (attempt {attempt+1}/{max_retries}): {e}"
                    logger.warning(error_msg)
                    if attempt == max_retries - 1:
                        state.add_error(error_msg)
                        state.telegram_sent = False
                        
        except Exception as e:
            state.add_error(f"Error sending Telegram message: {e}")
            state.telegram_sent = False
            
        return state
        
    def _format_summary_message(self, state):
        """
        Format summary data into a readable Telegram message
        Prioritizes core data and truncates LLM analysis if needed
        :param state: State object containing all summaries
        :return: Formatted message string (kept under 4096 chars)
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build core message (always include)
        account_number = self.settings.get('username', 'N/A')
        server_name = self.settings.get('server', 'N/A')
        core_message = f"<b>📊 Trading Summary</b> | Account {account_number} @ {server_name}\n"
        core_message += f"<i>{now}</i>\n\n"
        
        # Add account info if available
        account = self.get_account_info()
        if account:
            core_message += f"💰 <b>Account:</b> Balance: ${account['balance']:.2f} | Equity: ${account['equity']:.2f} | Free Margin: ${account['free_margin']:.2f}\n\n"
        
        # Check for recent untagged trades (last 24 hours)
        if hasattr(state, 'daily_summary') and state.daily_summary:
            daily_strategies = state.daily_summary.get('strategies', {})
            if 'Untagged (Old Trades)' in daily_strategies:
                untagged_count = daily_strategies['Untagged (Old Trades)']['trades']
                core_message += f"⚠️ <b>WARNING:</b> {untagged_count} untagged trade(s) detected today! Check your EA strategy tagging.\n\n"
        
        # Helper function to format summary section concisely
        def format_section(title, emoji, summary):
            pnl_emoji = "🟢" if summary['total_pnl'] >= 0 else "🔴"
            trades_count = summary['completed_trades']
            return (f"<b>{emoji} {title}</b>\n"
                f"{pnl_emoji} ${summary['total_pnl']} | "
                f"{trades_count} trades (W:{summary['winning_trades']} L:{summary['losing_trades']}) | "
                f"WR: {summary['win_rate']}%\n")
        
        # Show open trades section
        open_trades = self.get_open_positions()
        if open_trades:
            core_message += f"<b>🟡 Open Positions ({len(open_trades)})</b>\n"
            for trade in open_trades:
                pnl_emoji = "🟢" if trade['profit'] >= 0 else "🔴"
                core_message += (f"{pnl_emoji} <b>{trade['symbol']}</b> | "
                        f"Vol: {trade['volume']} | "
                        f"Entry: {trade['open_price']:.5f} | "
                        f"Current: {trade['current_price']:.5f} | "
                        f"P&L: ${trade['profit']:.2f} | "
                        f"Strategy: {trade['comment']}\n")
            core_message += "\n"

        # Add summaries
        if hasattr(state, 'daily_summary') and state.daily_summary:
            core_message += format_section("Today", "📅", state.daily_summary)
        
        if hasattr(state, 'weekly_summary') and state.weekly_summary:
            core_message += format_section("Week", "📆", state.weekly_summary)
        
        if hasattr(state, 'monthly_summary') and state.monthly_summary:
            core_message += format_section("Month", "📆", state.monthly_summary)
        
        if hasattr(state, 'yearly_summary') and state.yearly_summary:
            core_message += format_section("Year", "📆", state.yearly_summary)
            
            # Add strategy breakdown from yearly data (most comprehensive)
            strategies = state.yearly_summary.get('strategies', {})
            if strategies:
                core_message += f"\n<b>📈 Strategy Performance (YTD)</b>\n"
                # Filter out deposits/withdrawals and sort by PnL descending
                trading_strategies = {k: v for k, v in strategies.items() if k != 'Deposit/Withdrawal'}
                sorted_strategies = sorted(trading_strategies.items(), key=lambda x: x[1]['pnl'], reverse=True)
                
                # Allow configuring how many top strategies to show via settings
                top_n = self.settings.get('summary', {}).get('top_strategies', 5)

                for strategy, perf in sorted_strategies[:top_n]:
                    pnl_emoji = "🟢" if perf['pnl'] >= 0 else "🔴"
                    wr = (perf['wins'] / perf['trades'] * 100) if perf['trades'] > 0 else 0
                    core_message += (f"{pnl_emoji} <b>{strategy}</b>: "
                            f"${round(perf['pnl'], 2)} | "
                            f"{perf['trades']} trades | "
                            f"{round(wr, 1)}% WR | "
                            f"W:{perf['wins']} L:{perf['losses']}\n")
        
        # LLM Analysis - add with dynamic truncation
        if hasattr(state, 'llm_analysis') and state.llm_analysis:
            llm_header = "\n<b>🤖 AI Insights</b>\n<i>"
            llm_footer = "</i>\n"
            
            # Calculate remaining space for LLM analysis
            remaining_chars = 4096 - len(core_message) - len(llm_header) - len(llm_footer) - 50  # 50 char buffer
            
            if len(state.llm_analysis) > remaining_chars:
                truncated_analysis = state.llm_analysis[:remaining_chars] + "...[truncated]"
                core_message += llm_header + truncated_analysis + llm_footer
                logger.warning(f"LLM analysis truncated from {len(state.llm_analysis)} to {remaining_chars} chars")
            else:
                core_message += llm_header + state.llm_analysis + llm_footer
        
        return core_message
        
    def analyze_with_llm(self, state):
        """
        Analyze trading summaries using Ollama LLM for intelligent insights
        :param state: State object containing all summaries
        :return: Updated state with LLM analysis
        """
        # Check if Ollama is enabled
        if not self.settings.get('ollama', {}).get('enabled', False):
            state.add_message("Ollama analysis is disabled")
            state.llm_analysis = None
            logger.info("Ollama analysis is disabled")
            return state
        
        try:
            # Capture a single snapshot of current state
            snapshot = self._capture_snapshot()

            # Run safety pre-checks based on settings.summary.safety
            safety_allowed, safety_note = self._safety_check(snapshot)

            # Prepare the trading data for analysis using the same snapshot
            analysis_prompt = self._build_analysis_prompt(state, snapshot)
            
            if not safety_allowed and self.settings.get('summary', {}).get('safety', {}).get('enabled', False):
                analysis_prompt += "\n\nNOTE: Per safety policy, do NOT recommend closing any open position unless floating P&L is below the configured threshold. If asked, explicitly state that closes are suppressed by policy."
            
            # Get Ollama configuration
            model = self.settings['ollama'].get('model', 'llama3.2')
            base_url = self.settings['ollama'].get('base_url', 'http://localhost:11434')
            temperature = self.settings['ollama'].get('temperature', 0.7)
            system_prompt = self.settings['ollama'].get('system_prompt', 'You are an expert trading analyst.')
            timeout_seconds = self.settings['ollama'].get('timeout', 45)
            
            logger.info(f"Analyzing trading data with {model}...")
            
            # Call Ollama API with timeout
            try:
                with timeout(timeout_seconds):
                    response = ollama.chat(
                        model=model,
                        messages=[
                            {
                                'role': 'system',
                                'content': system_prompt
                            },
                            {
                                'role': 'user',
                                'content': analysis_prompt
                            }
                        ],
                        options={
                            'temperature': temperature
                        }
                    )
                    
                    # Extract the LLM's analysis
                    llm_analysis = response['message']['content']
                    
                    # If safety disallowed close recommendations, append the safety note
                    if not safety_allowed and safety_note:
                        llm_analysis = llm_analysis + f"\n\n[SAFETY] {safety_note}"

                    state.llm_analysis = llm_analysis
                    state.add_message("LLM analysis completed successfully")
                    logger.info("[OK] LLM analysis complete")
                    
            except TimeoutError as e:
                error_msg = f"LLM analysis timed out after {timeout_seconds} seconds"
                logger.error(error_msg)
                state.add_error(error_msg)
                state.llm_analysis = f"⚠️ Analysis timed out after {timeout_seconds}s - Please check Ollama service"
            
        except Exception as e:
            state.add_error(f"Error during LLM analysis: {e}")
            state.llm_analysis = None
            logger.error(f"Error during LLM analysis: {e}")
            
        return state

    def _safety_check(self, snapshot):
        """
        Evaluate safety thresholds from settings against the provided snapshot.
        Returns (allowed_to_recommend_closing: bool, note: str)
        """
        try:
            safety_cfg = self.settings.get('summary', {}).get('safety', {})
            if not safety_cfg.get('enabled', False):
                return True, ''

            # Retrieve thresholds
            close_if_loss_dollars = safety_cfg.get('close_if_loss_dollars', 0.0)
            close_if_loss_percent = safety_cfg.get('close_if_loss_percent', None)

            account = snapshot.get('account', {}) or {}
            balance = account.get('balance') if isinstance(account, dict) else None

            open_positions = snapshot.get('open_positions', []) or []
            
            # If there are no open positions, nothing to close
            if len(open_positions) == 0:
                return True, ''

            # Check each position against thresholds
            for pos in open_positions:
                profit = pos.get('profit', 0.0)
                
                # Dollar threshold: allow closing only if profit < close_if_loss_dollars
                if close_if_loss_dollars is not None:
                    try:
                        if float(profit) < float(close_if_loss_dollars):
                            note = f"Position {pos.get('symbol')} meets dollar threshold (P&L {profit} < {close_if_loss_dollars})"
                            logger.info(note)
                            return True, note
                    except Exception:
                        pass

                # Percent threshold (if configured and account balance available)
                if close_if_loss_percent is not None and balance is not None:
                    try:
                        thresh_amount = (abs(float(close_if_loss_percent)) / 100.0) * float(balance)
                        if float(profit) < -abs(thresh_amount):
                            note = f"Position {pos.get('symbol')} meets percent threshold (P&L {profit} < -{thresh_amount:.2f})"
                            logger.info(note)
                            return True, note
                    except Exception:
                        pass

            # If none of the positions met the threshold, do not allow recommends to close
            note = "No open position exceeded the configured safety thresholds; close recommendations suppressed."
            logger.info(note)
            return False, note
            
        except Exception as e:
            logger.error(f"Error during safety check: {e}")
            return True, ''
        
    def get_account_info(self):
        """Get current account balance and equity"""
        try:
            account_info = mt5.account_info()
            if account_info is None:
                return None
            return {
                'balance': account_info.balance,
                'equity': account_info.equity,
                'margin': account_info.margin,
                'free_margin': account_info.margin_free
            }
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None

    def _capture_snapshot(self):
        """Capture a consistent snapshot used for both message formatting and LLM analysis."""
        try:
            now = datetime.now()
            account = self.get_account_info()
            open_positions = self.get_open_positions()
            return {
                'now': now,
                'account': account,
                'open_positions': open_positions
            }
        except Exception as e:
            logger.error(f"Error capturing snapshot: {e}")
            return {'now': datetime.now(), 'account': None, 'open_positions': []}

    def _build_analysis_prompt(self, state, snapshot):
        """
        Build a comprehensive prompt for LLM analysis using a provided snapshot.
        :param state: State object containing summaries
        :param snapshot: dict with keys 'now', 'account', 'open_positions'
        :return: Formatted prompt string
        """
        now = snapshot.get('now', datetime.now())
        is_weekend = now.weekday() >= 5  # 5=Saturday, 6=Sunday

        prompt = "Analyze this forex trading performance:\n\n"

        if is_weekend:
            prompt += (
                "⚠️ TODAY IS WEEKEND - Forex markets are closed. Zero trades today is NORMAL and EXPECTED. "
                "DO NOT mention this as a concern.\n\n"
            )

        open_positions = snapshot.get('open_positions', [])
        if open_positions:
            prompt += f"**OPEN POSITIONS ({len(open_positions)}):**\n"
            total_exposure = 0
            for pos in open_positions:
                total_exposure += pos['profit']
                status = "WINNING" if pos['profit'] > 0 else "LOSING"
                prompt += (
                    f"- {pos['symbol']} [{status}]: "
                    f"Vol: {pos['volume']} | "
                    f"Entry: {pos['open_price']:.5f} | "
                    f"Current: {pos['current_price']:.5f} | "
                    f"Floating P&L: ${pos['profit']:.2f} | "
                    f"Strategy: {pos['comment']}\n"
                )
            prompt += f"Total Open Exposure: ${total_exposure:.2f}\n\n"
        else:
            prompt += "**OPEN POSITIONS:** None (all positions closed)\n\n"

        # Add daily summary
        if hasattr(state, 'daily_summary') and state.daily_summary:
            ds = state.daily_summary
            prompt += (
                f"**TODAY** P&L: ${ds['total_pnl']} | {ds['completed_trades']} trades | "
                f"Win Rate: {ds['win_rate']}% | Wins: {ds['winning_trades']} | Losses: {ds['losing_trades']}\n"
            )

        # Add weekly summary
        if hasattr(state, 'weekly_summary') and state.weekly_summary:
            ws = state.weekly_summary
            prompt += (
                f"**WEEK** P&L: ${ws['total_pnl']} | {ws['completed_trades']} trades | "
                f"Win Rate: {ws['win_rate']}% | Wins: {ws['winning_trades']} | Losses: {ws['losing_trades']}\n"
            )

        # Add monthly summary
        if hasattr(state, 'monthly_summary') and state.monthly_summary:
            ms = state.monthly_summary
            prompt += (
                f"**MONTH** P&L: ${ms['total_pnl']} | {ms['completed_trades']} trades | "
                f"Win Rate: {ms['win_rate']}% | Wins: {ms['winning_trades']} | Losses: {ms['losing_trades']}\n"
            )

        # Add yearly summary with strategy breakdown
        if hasattr(state, 'yearly_summary') and state.yearly_summary:
            ys = state.yearly_summary
            prompt += (
                f"**YEAR** P&L: ${ys['total_pnl']} | {ys['completed_trades']} trades | "
                f"Win Rate: {ys['win_rate']}% | Wins: {ys['winning_trades']} | Losses: {ys['losing_trades']}\n"
            )

            # Add top strategies with more detailed breakdown
            strategies = ys.get('strategies', {})
            if strategies:
                prompt += "\n**STRATEGY BREAKDOWN (Year-to-Date):**\n"
                # Filter out deposits/withdrawals
                trading_strategies = {k: v for k, v in strategies.items() if k != 'Deposit/Withdrawal'}
                sorted_strats = sorted(trading_strategies.items(), key=lambda x: x[1]['pnl'], reverse=True)

                for strategy, perf in sorted_strats[:5]:  # Top 5 strategies
                    wr = (perf['wins'] / perf['trades'] * 100) if perf['trades'] > 0 else 0
                    status = "PROFITABLE" if perf['pnl'] > 0 else "LOSING"
                    prompt += (
                        f"- {strategy} [{status}]: P&L ${round(perf['pnl'], 2)} | {perf['trades']} trades | "
                        f"{round(wr, 1)}% win rate | Wins: {perf['wins']} Losses: {perf['losses']}\n"
                    )

        prompt += (
            "\n⚠️ CONTEXT: 'Untagged (Old Trades)' = historical trades from BEFORE the strategy tagging system. "
            "These are LEGACY trades. Focus your analysis on CURRENT tagged strategies (Window_Breakout, Breakout, etc.) as they reflect the ACTIVE trading approach.\n"
        )

        # Determine if there are open positions using the snapshot
        has_open_positions = len(open_positions) > 0

        if has_open_positions:
            prompt += """\
MAX 800 CHARS. Give me:
1. **Key Insight** (1 line): Main takeaway
2. **Open Positions** (1 line): Quick risk check - hold or close?
3. **Risks** (1-2 lines): Biggest concerns
4. **Actions** (1-2 lines): What to do next

Be direct. Negative P&L = LOSING.
"""
        else:
            prompt += """\
MAX 800 CHARS. Give me:
1. **Key Insight** (1 line): Main takeaway
2. **Best Performers** (1-2 lines): Only list strategies with POSITIVE P&L. If none, say "No profitable tagged strategies yet"
3. **Risks** (1-2 lines): Biggest concerns
4. **Actions** (1-2 lines): What to do next

Be direct. Negative P&L = LOSING.
"""

        return prompt