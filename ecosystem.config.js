// PM2 supervises `start.sh`, which runs `uv run -- uvicorn src.main:app
// --workers N`. PM2 itself doesn't speak ASGI — uvicorn is still the actual
// server; PM2 just keeps it alive, manages logs, and restarts it on crash or
// on `pm2 startOrReload`, the same role gunicorn would otherwise play here.
module.exports = {
  apps: [
    {
      name: "albaddar-prod",
      script: "./start.sh",
      interpreter: "bash",
      // __dirname always resolves to wherever this file itself lives, so
      // this stays correct whether it's your self-hosted runner's checkout
      // path (which lives under actions-runner/_work/... and isn't fixed)
      // or a manual clone anywhere else — no hardcoded path needed.
      cwd: __dirname,
      // start.sh forks its own uvicorn worker processes — PM2 should run
      // exactly one instance of the supervisor script, not fork this itself.
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      env: {
        PORT: "",
        UVICORN_WORKERS: "4",
        DATABASE_URL: "",
        MEDIA_FOLDER: "",
        DOMAIN: "",
      },
      out_file: "./logs/prod-out.log",
      error_file: "./logs/prod-error.log",
      merge_logs: true,
      time: true,
    },
  ],
};
