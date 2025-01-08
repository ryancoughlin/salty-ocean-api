module.exports = {
    apps: [{ 
        name: "salty-server",
        script: "app.js", 
        interpreter: '/usr/bin/node', 
        instances: 1,
        autorestart: true,
        env: { NODE_ENV: "production", PORT: 5010 } 
    }]
}
