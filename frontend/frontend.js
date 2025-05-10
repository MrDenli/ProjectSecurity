const express = require('express');
const axios = require('axios');
const app = express();
const PORT = 3000;

app.get('/', async (req, res) => {
    try {
        const response = await axios.get('http://backend-service:8000');
        res.send(`Frontend received: ${response.data}`);
    } catch (error) {
        res.status(500).send('Error contacting backend');
    }
});

app.listen(PORT, () => {
    console.log(`Serving at port ${PORT}`);
});