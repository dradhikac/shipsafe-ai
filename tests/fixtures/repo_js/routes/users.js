const express = require('express');
const router = express.Router();

router.get('/profile', (req, res) => {
    // Contract violation: returns snake_case 'user_id' instead of specified 'userId'
    res.json({
        user_id: "usr_12345",
        displayName: "Jane Doe"
    });
});

module.exports = router;
