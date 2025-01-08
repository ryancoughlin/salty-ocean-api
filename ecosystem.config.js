module.exports = {
    apps: [{ 
        name: "salty-server",
        script: "app.js", 
        interpreter: '/root/.nvm/versions/node/v18.20.5/bin/node',
        env: {
            NODE_ENV: "production",
            PATH: "/root/.nvm/versions/node/v18.20.5/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            NVM_DIR: "/root/.nvm",
            PORT: 5010
        },
        exec_mode: "cluster",
        instances: "max"
    }]
}
