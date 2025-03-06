async function fetchStream(url) {
    const response = await fetch(url);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let jsonData = "";
    let isFirstChunk = true;

    while (true) {
        const { done, value } = await reader.read();
        if (done) {
            console.log("Stream finished.");
            break;
        }

        jsonData += decoder.decode(value);

        try {
            if (isFirstChunk) {
                jsonData = jsonData.replace('{"updates": [', "[");  // ✅ Handle initial chunk
                isFirstChunk = false;
            }

            if (jsonData.endsWith("]}")) {
                const parsedData = JSON.parse(jsonData);
                console.log("Final JSON:", parsedData);
                break;
            } else {
                console.log("Streaming JSON chunk received:", jsonData);
            }
        } catch (e) {
            console.log("Waiting for more JSON data...");
        }
    }
}

const testUrl = 'http://127.0.0.1:3001/run-vivarium?duration=10&vivarium_id=vivarium-8463a3ef-5632-4e92-b04a-076b62deb3f3-395354397'