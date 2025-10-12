# MT5 Trading Summary with AI Analysis

An intelligent MetaTrader 5 trading summary system that provides automated performance analysis using local LLMs via Ollama, with Telegram notifications.

## 🎯 Features

- **Automated MT5 Connection**: Connects to MetaTrader 5 and retrieves trade history
- **Multi-Timeframe Summaries**: Daily, weekly, monthly, and yearly performance metrics
- **AI-Powered Analysis**: Uses Ollama LLM to provide intelligent insights and recommendations
- **Telegram Notifications**: Sends formatted summaries with AI analysis to your Telegram
- **Scheduled Execution**: Runs automatically at configured times (default: 5 PM daily)
- **Manual Execution**: Can be run on-demand for immediate reports

## 📋 Requirements

- Python 3.7+
- MetaTrader 5 terminal (broker-specific installation)
- Ollama installed and running locally
- Telegram Bot (optional, for notifications)

## 🚀 Installation

### 1. Clone and Setup Virtual Environment

```powershell
cd C:\Mac\Home\Documents\code\trade_summary
python -m venv trading_summary
.\trading_summary\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install MetaTrader5 requests ollama
```

### 3. Install and Configure Ollama

1. Download and install Ollama from [ollama.ai](https://ollama.ai)
2. Pull your preferred model:
   ```powershell
   ollama pull llama3.2
   ```
3. Ensure Ollama is running (it runs as a service by default)

### 4. Configure Settings

Edit `settings.json`:

```json
{
    "mt5": {
        "server": "YOUR_BROKER_SERVER",
        "username": "YOUR_MT5_ACCOUNT",
        "password": "YOUR_PASSWORD",
        "mt5_pathway": "C:/Path/To/Your/Broker/terminal64.exe"
    },
    "telegram": {
        "enabled": true,
        "bot_token": "YOUR_BOT_TOKEN",
        "chat_id": "YOUR_CHAT_ID"
    },
    "ollama": {
        "enabled": true,
        "model": "llama3.2",
        "base_url": "http://localhost:11434",
        "temperature": 0.7
    },
    "scheduler": {
        "run_hour": 17,
        "run_minute": 0
    }
}
```

#### Getting Telegram Credentials:
1. Talk to [@BotFather](https://t.me/botfather) to create a bot
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)

## 📖 Usage

### Run Immediately (Testing)
```powershell
python main.py --now
```

### Run Scheduler (Production)
```powershell
python main.py
```

### Show Help
```powershell
python main.py --help
```

## 🔧 Configuration Options

### Ollama Settings

- **enabled**: Enable/disable AI analysis (true/false)
- **model**: Which Ollama model to use (llama3.2, mistral, codellama, etc.)
- **base_url**: Ollama API endpoint (default: http://localhost:11434)
- **temperature**: Creativity level for analysis (0.0-1.0)
- **system_prompt**: Custom prompt to guide the AI's analysis style

### Scheduler Settings

- **run_hour**: Hour to run daily (0-23, 24-hour format)
- **run_minute**: Minute to run (0-59)
- **timezone**: "local" for system timezone

## 📊 What You Get

### Trading Metrics
- Total trades and P/L for each period
- Win/loss breakdown
- Win rate percentages
- Comparative analysis across timeframes

### AI Analysis Includes
1. **Performance Overview**: Overall assessment
2. **Key Strengths**: What's working well
3. **Areas of Concern**: Risk factors and red flags
4. **Trends & Patterns**: Cross-timeframe insights
5. **Risk Assessment**: Risk management evaluation
6. **Actionable Recommendations**: Specific improvement suggestions

## 🏗️ Project Structure

```
trade_summary/
├── main.py                          # Entry point and scheduler
├── SummaryAgentNodes.py             # Core agent with MT5 and LLM logic
├── SummaryAgentNodesWorkflow.py     # Workflow orchestration
├── State.py                         # State management
├── settings.json                    # Configuration
└── trading_summary/                 # Virtual environment
```

## 🛠️ Workflow Steps

1. **Initialize MT5** - Connect and login to MetaTrader 5
2. **Daily Summary** - Retrieve and analyze today's trades
3. **Weekly Summary** - Week-to-date performance
4. **Monthly Summary** - Month-to-date performance
5. **Yearly Summary** - Year-to-date performance
6. **AI Analysis** - LLM analyzes all data and provides insights
7. **Send to Telegram** - Delivers formatted report with AI insights
8. **Shutdown** - Clean MT5 connection closure

## 🔒 Security Notes

- Never commit `settings.json` with real credentials
- Keep your Telegram bot token private
- MT5 passwords are stored in plain text - use appropriate file permissions

## 🐛 Troubleshooting

### MT5 Connection Issues
- Ensure MT5 terminal is running
- Verify the `mt5_pathway` points to the correct broker's terminal64.exe
- Check that credentials match your MT5 account

### Ollama Issues
- Verify Ollama is running: `ollama list`
- Check model is downloaded: `ollama pull llama3.2`
- Test connection: `curl http://localhost:11434/api/tags`

### Telegram Not Sending
- Verify bot token and chat ID are correct
- Ensure you've started a conversation with your bot
- Check internet connection

## 📝 Example Output

```
📊 Trading Summary Report
Generated: 2025-10-11 17:00:00

📅 Today
🟢 Profit: $250.50
📈 Trades: 5 (W: 3, L: 2)
🎯 Win Rate: 60.0%

📆 This Week
🟢 Profit: $1,200.00
📈 Trades: 28 (W: 18, L: 10)
🎯 Win Rate: 64.3%

🤖 AI Analysis
Performance Overview: Strong positive performance this week with 
consistent profits. Your win rate of 64.3% is above average...

Key Strengths:
• Excellent risk-to-reward ratio
• Consistent daily profits
• Improving win rate trend

Areas of Concern:
• Slight decrease in daily volume
• Consider reviewing Friday trades

Recommendations:
1. Maintain current position sizing
2. Review losing trades for patterns
3. Consider taking profits earlier on volatile pairs
```

## 🤝 Contributing

Feel free to fork and customize for your trading needs!

---

**Disclaimer**: This tool is for informational purposes only. Past performance does not guarantee future results. Trade responsibly.
