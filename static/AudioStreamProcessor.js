class AudioStreamProcessor extends AudioWorkletProcessor {
    static get parameterDescriptors() {
        return [{
            name: 'my processor',
            defaultValue: 0
        }];
    }

    constructor() {
        super();
        this._bufferSize = 2048;
        this._buffer = new Float32Array(this._bufferSize);
        this._initBuffer();
    }

    _initBuffer() {
        this._bytesWritten = 0;
    }

    _isBufferEmpty() {
        return this._bytesWritten === 0;
    }

    _isBufferFull() {
        return this._bytesWritten === this._bufferSize;
    }

    _appendToBuffer(value) {
        if (this._isBufferFull()) {
            this._flush();
        }

        if (!value) return;
        for (let i = 0; i < value.length; i++) {
            this._buffer[this._bytesWritten++] = value[i];
        }
    }

    _flush() {
        let buffer = this._buffer;
        if (this._bytesWritten < this._bufferSize) {
            buffer = buffer.slice(0, this._bytesWritten);
        }

        this.port.postMessage({
            eventType: 'data',
            audioBuffer: buffer
        });

        this._initBuffer();
    }

    process(inputs, outputs, parameters) {


        if (this._isBufferFull()) {
            this._flush();
        } else {
            this._appendToBuffer(inputs[0][0]);
        }

        return true;
    }

}

registerProcessor('AudioStream', AudioStreamProcessor);