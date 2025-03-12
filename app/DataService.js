class VivariumService {
    constructor(root= 'http://127.0.0.1:3001') {
        this.root = root;
        this.testId = 'test';
    }

    formatUrl(root, duration, id) {
        return `${root}/run-vivarium?duration=${duration}&vivarium_id=${id}`;
    }

    async fetchStream(url) {
        const response = await fetch(url);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let jsonData = "";
        let isFirstChunk = true;

        while (true) {
            const {done, value} = await reader.read();
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

    submitRequest(duration, id) {
        const url = this.formatUrl(this.root, duration, id);
        return this.fetchStream(url);
    }

    sendTestRequest(duration) {
        return this.submitRequest(duration, this.testId);
    }
}