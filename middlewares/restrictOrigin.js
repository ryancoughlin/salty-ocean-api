const cors = require("cors");

const corsOptions = {
  origin: [
    "http://localhost:5173",
    "https://saltyoffshore.com",
    "https://www.saltyoffshore.com",
    "https://conditions.saltyoffshore.com",
  ],
  methods: ["GET", "OPTIONS"],
  optionsSuccessStatus: 200, // some legacy browsers (IE11, various SmartTVs) choke on 204
};

module.exports = cors(corsOptions);
