const path = require('path');
const fs = require('fs');

// Load .env manually
const envFile = path.join(__dirname, '.env');
const envVars = {};
if (fs.existsSync(envFile)) {
  fs.readFileSync(envFile, 'utf8').split('\n').forEach(line => {
    const match = line.match(/^([^#=]+)=(.*)$/);
    if (match) envVars[match[1].trim()] = match[2].trim();
  });
}

module.exports = {
  apps: [{
    name: 'weatherbot',
    script: '.venv/bin/python',
    args: '-m uvicorn src.main:app --host 0.0.0.0 --port 6010',
    cwd: '/data/.openclaw/workspace/projects/weatherbot',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env: {
      PYTHONPATH: '/data/.openclaw/workspace/projects/weatherbot',
      DB_URL: 'postgresql://node@localhost:5432/polyedge',
      MODE: 'paper',
      TELEGRAM_BOT_TOKEN: envVars.TELEGRAM_BOT_TOKEN || '',
      TELEGRAM_ADMIN_CHAT_ID: envVars.TELEGRAM_ADMIN_CHAT_ID || envVars.TELEGRAM_CHAT_ID || '',
      ODDS_API_KEY: envVars.ODDS_API_KEY || '',
    },
    error_file: './logs/error.log',
    out_file: './logs/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
  }]
};
