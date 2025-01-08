module.exports = {
    apps: [{ 
        name: "salty-server",
        script: "app.js", 
        interpreter: '/root/.nvm/versions/node/v18.20.5/bin/node',
        instances: 1,
        autorestart: true,
        env: { NODE_ENV: "production", PORT: 5010 } 
    }]
}
