module.exports = {
  apps: [{
    name: 'weatherbot',
    script: './start.sh',
    cwd: '/data/.openclaw/workspace/projects/weatherbot',
    instances: 1,
    autorestart: true,
    watch: false,
    max_restarts: 10,
    min_uptime: '10s',
    max_memory_restart: '512M',
    restart_delay: 5000,
    env: {
      NODE_ENV: 'production',
      PORT: 6010,
    },
    error_file: './logs/error.log',
    out_file: './logs/out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true,
  }]
};
