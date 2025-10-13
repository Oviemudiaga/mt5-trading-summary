
"""
SummaryAgent - A class for managing MetaTrader 5 connection and trade summaries
"""
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import requests
import ollama


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
        
    def initialize_mt5(self, state):
        """
        Initialize connection with the MetaTrader 5 terminal
        :param state: State object to track workflow
        :return: Updated state
        """
        try:
            # Get credentials
            mt5_pathway = self.settings['mt5']['mt5_pathway']
            username = int(self.settings['mt5']['username'])
            password = self.settings['mt5']['password']
            server = self.settings['mt5']['server']
            
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
                state.messages.append(f"MetaTrader 5 initialized and logged in successfully (Account: {username})")
                state.mt5_connected = True
                state.logged_in = True
                print("MetaTrader5 package author:", mt5.__author__)
                print("MetaTrader5 package version:", mt5.__version__)
                print(f"Logged in to account: {username} on server: {server}")
            else:
                error_code = mt5.last_error()
                state.messages.append(f"MT5 initialization failed, error code: {error_code}")
                state.mt5_connected = False
                state.logged_in = False
                print(f"initialize() failed, error code = {error_code}")
                
        except Exception as e:
            state.messages.append(f"Error initializing MetaTrader 5: {e}")
            state.mt5_connected = False
            state.logged_in = False
            print(f"Error initializing MetaTrader 5: {e}")
            
        return state
    
    def login_mt5(self, state):
        """
        Log into MT5 with credentials
        :param state: State object to track workflow
        :return: Updated state
        """
        if not state.mt5_connected:
            state.messages.append("Cannot login - MT5 not initialized")
            return state
            
        try:
            # Ensure that all variables are set to the correct type
            username = int(self.settings['mt5']['username'])
            password = self.settings['mt5']['password']
            server = self.settings['mt5']['server']
            
            # Attempt to login to MT5
            mt5_login = mt5.login(
                login=username,
                password=password,
                server=server
            )
            
            if mt5_login:
                self.logged_in = True
                state.logged_in = True
                state.messages.append(f"Successfully logged into MT5 account: {username}")
                print(f"Logged in to MT5 account: {username}")
            else:
                error_code = mt5.last_error()
                state.logged_in = False
                state.messages.append(f"MT5 login failed, error code: {error_code}")
                print(f"login() failed, error code = {error_code}")
                
        except Exception as e:
            state.logged_in = False
            state.messages.append(f"Error logging into MetaTrader 5: {e}")
            print(f"Error logging into MetaTrader 5: {e}")
            
        return state
    
    def get_trade_history(self, from_date, to_date):
        """
        Retrieve trade history from MT5
        :param from_date: Start date for history
        :param to_date: End date for history
        :return: List of deals or None if error
        """
        try:
            # Debug: Print the date range being queried
            print(f"  Querying deals from {from_date} to {to_date}")
            
            # Get deals in the specified time range
            deals = mt5.history_deals_get(from_date, to_date)
            
            if deals is None:
                print(f"No deals found, error code: {mt5.last_error()}")
                return None
            elif len(deals) == 0:
                print("No deals found in the specified time range")
                return []
            
            return list(deals)
            
        except Exception as e:
            print(f"Error retrieving trade history: {e}")
            return None
        
    def get_open_positions(self):
        """
        Get currently open positions from MT5
        :return: List of open position dictionaries
        """
        try:
            positions = mt5.positions_get()
            
            if positions is None:
                print(f"No positions found, error code: {mt5.last_error()}")
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
            
            return open_trades
            
        except Exception as e:
            print(f"Error retrieving open positions: {e}")
            return []    
    
    
    def calculate_summary(self, deals):
        """
        Calculate summary statistics from deals
        :param deals: List of deals from MT5
        :return: Dictionary with summary statistics including strategy breakdown
        """
        if not deals:
            return {
                'total_deals': 0,
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
            elif hasattr(deal, 'entry') and deal.entry == 1:
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
        total_trades = 0
        for pos_id in round_trip_ids:
            entry_deal = position_entries[pos_id]
            exit_deal = position_exits[pos_id]
            profit = exit_deal.profit
            swap = exit_deal.swap if hasattr(exit_deal, 'swap') else 0.0
            commission = exit_deal.commission if hasattr(exit_deal, 'commission') else 0.0
            fee = exit_deal.fee if hasattr(exit_deal, 'fee') else 0.0
            comment = exit_deal.comment if hasattr(exit_deal, 'comment') else ''
            # Recover strategy if SL/TP
            if '[sl ' in str(comment).lower() or '[tp ' in str(comment).lower():
                if pos_id in position_strategy_map:
                    comment = position_strategy_map[pos_id]
            # Categorize strategy with clear labels
            if 'CheckoutSC' in str(comment) or 'Checkout' in str(comment):
                strategy = 'Deposit/Withdrawal'
            elif not comment or not str(comment).strip():
                strategy = 'Untagged (Old Trades)'
            else:
                strategy = comment
            if strategy not in strategies:
                strategies[strategy] = {
                    'trades': 0,
                    'pnl': 0.0,
                    'wins': 0,
                    'losses': 0
                }
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
            total_trades += 1

        # Calculate total P&L (profit + swap - commission - fee)
        total_pnl = total_profit + total_swap - total_commission - total_fee
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        return {
            'total_deals': total_trades,
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
            state.messages.append("Cannot get daily summary - not logged in")
            return state
        
        try:
            # Get today's date range
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            now = datetime.now()
            
            deals = self.get_trade_history(today, now)
            summary = self.calculate_summary(deals)
            
            state.daily_summary = summary
            state.messages.append(f"Daily summary: {summary}")
            print(f"Daily Summary: Total P&L: ${summary['total_pnl']}, Trades: {summary['total_deals']}")
            
            # Check for untagged trades (warning system)
            if 'Untagged (Old Trades)' in summary.get('strategies', {}):
                untagged_count = summary['strategies']['Untagged (Old Trades)']['trades']
                print(f"⚠️  WARNING: {untagged_count} untagged trade(s) detected today! Check your EA strategy tagging.")
                state.messages.append(f"WARNING: {untagged_count} untagged trades detected")
            
        except Exception as e:
            state.messages.append(f"Error getting daily summary: {e}")
            print(f"Error getting daily summary: {e}")
            
        return state
    
    def summarize_week(self, state):
        """
        Summarize trading results for the week to date
        :param state: State object to track workflow
        :return: Updated state
        """
        if not state.logged_in:
            state.messages.append("Cannot get weekly summary - not logged in")
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
            state.messages.append(f"Weekly summary: {summary}")
            print(f"Weekly Summary: Total P&L: ${summary['total_pnl']}, Trades: {summary['total_deals']}")
            
        except Exception as e:
            state.messages.append(f"Error getting weekly summary: {e}")
            print(f"Error getting weekly summary: {e}")
            
        return state
    
    def summarize_month(self, state):
        """
        Summarize trading results for the month to date
        :param state: State object to track workflow
        :return: Updated state
        """
        if not state.logged_in:
            state.messages.append("Cannot get monthly summary - not logged in")
            return state
        
        try:
            # Get month start
            today = datetime.now()
            month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            now = datetime.now()
            
            deals = self.get_trade_history(month_start, now)
            summary = self.calculate_summary(deals)
            
            state.monthly_summary = summary
            state.messages.append(f"Monthly summary: {summary}")
            print(f"Monthly Summary: Total P&L: ${summary['total_pnl']}, Trades: {summary['total_deals']}")
            
        except Exception as e:
            state.messages.append(f"Error getting monthly summary: {e}")
            print(f"Error getting monthly summary: {e}")
            
        return state
    
    def summarize_year(self, state):
        """
        Summarize trading results for the year to date
        :param state: State object to track workflow
        :return: Updated state
        """
        if not state.logged_in:
            state.messages.append("Cannot get yearly summary - not logged in")
            return state
        
        try:
            # Get year start
            today = datetime.now()
            year_start = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            now = datetime.now()
            
            deals = self.get_trade_history(year_start, now)
            summary = self.calculate_summary(deals)
            
            state.yearly_summary = summary
            state.messages.append(f"Yearly summary: {summary}")
            print(f"Yearly Summary: Total P&L: ${summary['total_pnl']}, Trades: {summary['total_deals']}")
            
        except Exception as e:
            state.messages.append(f"Error getting yearly summary: {e}")
            print(f"Error getting yearly summary: {e}")
            
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
            state.messages.append("MT5 connection shutdown successfully")
            print("MT5 connection shutdown")
            
        except Exception as e:
            state.messages.append(f"Error shutting down MT5: {e}")
            print(f"Error shutting down MT5: {e}")
            
        return state
    
    def send_telegram_summary(self, state):
        """
        Send all summaries to Telegram account
        :param state: State object containing all summaries
        :return: Updated state
        """
        try:
            bot_token = self.settings['telegram']['bot_token']
            chat_id = self.settings['telegram']['chat_id']
            
            # Format the message
            message = self._format_summary_message(state)
            
            # Telegram has a 4096 character limit
            if len(message) > 4096:
                # Truncate the LLM analysis if message is too long
                print("⚠ Message too long, truncating...")
                message = message[:4000] + "\n\n...(message truncated)"
            
            # Send via Telegram API
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                state.messages.append("Summary sent to Telegram successfully")
                state.telegram_sent = True
                print("Summary sent to Telegram successfully")
            else:
                state.messages.append(f"Failed to send Telegram message: {response.text}")
                state.telegram_sent = False
                print(f"Failed to send Telegram message: {response.text}")
                
        except Exception as e:
            state.messages.append(f"Error sending Telegram message: {e}")
            state.telegram_sent = False
            print(f"Error sending Telegram message: {e}")
            
        return state
    def _format_summary_message(self, state):
        """
        Format summary data into a readable Telegram message
        :param state: State object containing all summaries
        :return: Formatted message string (kept under 4096 chars)
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = f"<b>📊 Trading Summary</b> | {now}\n\n"
        
        # Add account info if available
        account = self.get_account_info()
        if account:
            message += f"💰 <b>Account:</b> Balance: ${account['balance']:.2f} | Equity: ${account['equity']:.2f} | Free Margin: ${account['free_margin']:.2f}\n\n"
        
        # Check for recent untagged trades (last 24 hours)
        if hasattr(state, 'daily_summary') and state.daily_summary:
            daily_strategies = state.daily_summary.get('strategies', {})
            if 'Untagged (Old Trades)' in daily_strategies:
                untagged_count = daily_strategies['Untagged (Old Trades)']['trades']
                message += f"⚠️ <b>WARNING:</b> {untagged_count} untagged trade(s) detected today! Check your EA strategy tagging.\n\n"
        
        # Helper function to format summary section concisely
        def format_section(title, emoji, summary):
            pnl_emoji = "🟢" if summary['total_pnl'] >= 0 else "🔴"
            trades_count = summary['total_deals']  # This is already round-trip count
            return (f"<b>{emoji} {title}</b>\n"
                f"{pnl_emoji} ${summary['total_pnl']} | "
                f"{trades_count} trades (W:{summary['winning_trades']} L:{summary['losing_trades']}) | "
                f"WR: {summary['win_rate']}%\n")
        
        # Show open trades section
        open_trades = self.get_open_positions()
        if open_trades:
            message += f"<b>🟡 Open Positions ({len(open_trades)})</b>\n"
            for trade in open_trades:
                pnl_emoji = "🟢" if trade['profit'] >= 0 else "🔴"
                message += (f"{pnl_emoji} <b>{trade['symbol']}</b> | "
                        f"Vol: {trade['volume']} | "
                        f"Entry: {trade['open_price']:.5f} | "
                        f"Current: {trade['current_price']:.5f} | "
                        f"P&L: ${trade['profit']:.2f} | "
                        f"Strategy: {trade['comment']}\n")
            message += "\n"

        # Add summaries
        if hasattr(state, 'daily_summary') and state.daily_summary:
            message += format_section("Today", "📅", state.daily_summary)
        
        if hasattr(state, 'weekly_summary') and state.weekly_summary:
            message += format_section("Week", "📆", state.weekly_summary)
        
        if hasattr(state, 'monthly_summary') and state.monthly_summary:
            message += format_section("Month", "📆", state.monthly_summary)
        
        if hasattr(state, 'yearly_summary') and state.yearly_summary:
            message += format_section("Year", "📆", state.yearly_summary)
            
            # Add strategy breakdown from yearly data (most comprehensive)
            strategies = state.yearly_summary.get('strategies', {})
            if strategies:
                message += f"\n<b>📈 Strategy Performance (YTD)</b>\n"
                # Filter out deposits/withdrawals and sort by PnL descending
                trading_strategies = {k: v for k, v in strategies.items() if k != 'Deposit/Withdrawal'}
                sorted_strategies = sorted(trading_strategies.items(), key=lambda x: x[1]['pnl'], reverse=True)
                
                for strategy, perf in sorted_strategies[:5]:  # Top 5 strategies to save space
                    pnl_emoji = "🟢" if perf['pnl'] >= 0 else "🔴"
                    wr = (perf['wins'] / perf['trades'] * 100) if perf['trades'] > 0 else 0
                    message += (f"{pnl_emoji} <b>{strategy}</b>: "
                            f"${round(perf['pnl'], 2)} | "
                            f"{perf['trades']} trades | "
                            f"{round(wr, 1)}% WR | "
                            f"W:{perf['wins']} L:{perf['losses']}\n")
        
        # LLM Analysis - truncate if needed
        if hasattr(state, 'llm_analysis') and state.llm_analysis:
            message += f"\n<b>🤖 AI Insights</b>\n<i>{state.llm_analysis}</i>\n"
        
        # Hard limit to 4000 chars (leaving buffer for safety)
        if len(message) > 4000:
            message = message[:3990] + "\n\n...[truncated]"
        
        return message   
    def analyze_with_llm(self, state):
        """
        Analyze trading summaries using Ollama LLM for intelligent insights
        :param state: State object containing all summaries
        :return: Updated state with LLM analysis
        """
        # Check if Ollama is enabled
        if not self.settings.get('ollama', {}).get('enabled', False):
            state.messages.append("Ollama analysis is disabled")
            state.llm_analysis = None
            return state
        
        try:
            # Prepare the trading data for analysis
            analysis_prompt = self._build_analysis_prompt(state)
            
            # Get Ollama configuration
            model = self.settings['ollama'].get('model', 'llama3.2')
            base_url = self.settings['ollama'].get('base_url', 'http://localhost:11434')
            temperature = self.settings['ollama'].get('temperature', 0.7)
            system_prompt = self.settings['ollama'].get('system_prompt', 'You are an expert trading analyst.')
            
            print(f"Analyzing trading data with {model}...")
            
            # Call Ollama API
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
            
            state.llm_analysis = llm_analysis
            state.messages.append("LLM analysis completed successfully")
            print("✓ LLM analysis complete")
            
        except Exception as e:
            state.messages.append(f"Error during LLM analysis: {e}")
            state.llm_analysis = None
            print(f"Error during LLM analysis: {e}")
            
        return state
    
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
            print(f"Error getting account info: {e}")
            return None

    def _build_analysis_prompt(self, state):
        """
        Build a comprehensive prompt for LLM analysis
        :param state: State object containing all summaries
        :return: Formatted prompt string
        """
        # Check if it's weekend
        now = datetime.now()
        is_weekend = now.weekday() >= 5  # 5=Saturday, 6=Sunday
        
        prompt = "Analyze this forex trading performance:\n\n"
        
        if is_weekend:
            prompt += "⚠️ TODAY IS WEEKEND - Forex markets are closed. Zero trades today is NORMAL and EXPECTED. DO NOT mention this as a concern.\n\n"
        
        open_positions = self.get_open_positions()
        if open_positions:
            prompt += f"**OPEN POSITIONS ({len(open_positions)}):**\n"
            total_exposure = 0
            for pos in open_positions:
                total_exposure += pos['profit']
                status = "WINNING" if pos['profit'] > 0 else "LOSING"
                prompt += (f"- {pos['symbol']} [{status}]: "
                        f"Vol: {pos['volume']} | "
                        f"Entry: {pos['open_price']:.5f} | "
                        f"Current: {pos['current_price']:.5f} | "
                        f"Floating P&L: ${pos['profit']:.2f} | "
                        f"Strategy: {pos['comment']}\n")
            prompt += f"Total Open Exposure: ${total_exposure:.2f}\n\n"
        else:
            prompt += "**OPEN POSITIONS:** None (all positions closed)\n\n"        
               
        # Add daily summary
        if hasattr(state, 'daily_summary') and state.daily_summary:
            ds = state.daily_summary
            prompt += f"**TODAY** P&L: ${ds['total_pnl']} | {ds['total_deals']} trades | Win Rate: {ds['win_rate']}% | Wins: {ds['winning_trades']} | Losses: {ds['losing_trades']}\n"
        
        # Add weekly summary
        if hasattr(state, 'weekly_summary') and state.weekly_summary:
            ws = state.weekly_summary
            prompt += f"**WEEK** P&L: ${ws['total_pnl']} | {ws['total_deals']} trades | Win Rate: {ws['win_rate']}% | Wins: {ws['winning_trades']} | Losses: {ws['losing_trades']}\n"
        
        # Add monthly summary
        if hasattr(state, 'monthly_summary') and state.monthly_summary:
            ms = state.monthly_summary
            prompt += f"**MONTH** P&L: ${ms['total_pnl']} | {ms['total_deals']} trades | Win Rate: {ms['win_rate']}% | Wins: {ms['winning_trades']} | Losses: {ms['losing_trades']}\n"
        
        # Add yearly summary with strategy breakdown
        if hasattr(state, 'yearly_summary') and state.yearly_summary:
            ys = state.yearly_summary
            prompt += f"**YEAR** P&L: ${ys['total_pnl']} | {ys['total_deals']} trades | Win Rate: {ys['win_rate']}% | Wins: {ys['winning_trades']} | Losses: {ys['losing_trades']}\n"
            
            # Add top strategies with more detailed breakdown
            strategies = ys.get('strategies', {})
            if strategies:
                prompt += f"\n**STRATEGY BREAKDOWN (Year-to-Date):**\n"
                # Filter out deposits/withdrawals
                trading_strategies = {k: v for k, v in strategies.items() if k != 'Deposit/Withdrawal'}
                sorted_strats = sorted(trading_strategies.items(), key=lambda x: x[1]['pnl'], reverse=True)
                
                for strategy, perf in sorted_strats[:5]:  # Top 5 strategies
                    wr = (perf['wins'] / perf['trades'] * 100) if perf['trades'] > 0 else 0
                    status = "PROFITABLE" if perf['pnl'] > 0 else "LOSING"
                    prompt += (f"- {strategy} [{status}]: "
                            f"P&L ${round(perf['pnl'], 2)} | "
                            f"{perf['trades']} trades | "
                            f"{round(wr, 1)}% win rate | "
                            f"Wins: {perf['wins']} Losses: {perf['losses']}\n")
                
        prompt += "\n⚠️ CONTEXT: 'Untagged (Old Trades)' = historical trades from BEFORE the strategy tagging system. These are LEGACY trades. Focus your analysis on CURRENT tagged strategies (Window_Breakout, Breakout, etc.) as they reflect the ACTIVE trading approach.\n"
                
        # Determine if there are open positions
        has_open_positions = len(self.get_open_positions()) > 0

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