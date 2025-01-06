replacement = """
        try {
            var fs = require('fs');
            var https = require('https');
            _cr = {
                key: fs.readFileSync('./ssl/server.key', 'utf8'),
                cert: fs.readFileSync('./ssl/server.crt', 'utf8')
            };
        } catch (e) {
            console.error("Failed to load SSL cert:", e);
            _cr = { };
        }
        var sserver = https.createServer(_cr, app);
"""

with open("server.js", "r") as file:
    lines = file.readlines()

with open("server.js", "w") as file:
    for line in lines:
        if "var sserver = https.createServer(app);" in line:
            file.write(replacement + "\n")
        else:
            file.write(line)


# import time
# print("finished")
# print("now sleeping for 600 seconds")   
# time.sleep(600)