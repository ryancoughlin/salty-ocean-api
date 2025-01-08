const os = require('os');

function getLocalIpAddress() {
  const interfaces = os.networkInterfaces();
  for (const interfaceName of Object.keys(interfaces)) {
    const addresses = interfaces[interfaceName];
    for (const addr of addresses) {
      if (addr.family === 'IPv4' && !addr.internal) {
        return addr.address;
      }
    }
  }
  return 'localhost';
}

process.stdin.pipe(process.stdout);

const port = process.env.PORT || 3000;
const ip = getLocalIpAddress();

console.log(`\n🚀 Server running at:`);
console.log(`- Local:   http://localhost:${port}`);
console.log(`- Network: http://${ip}:${port}\n`); 