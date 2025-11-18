package com.example;

import jakarta.servlet.ServletOutputStream;
import jakarta.servlet.WriteListener;
import java.io.ByteArrayOutputStream;
import java.io.IOException;

public class CopyOutputStream extends ServletOutputStream {
    private ServletOutputStream origStream;
    private ByteArrayOutputStream copyStream;

    public CopyOutputStream(ServletOutputStream origStream){
        this.origStream = origStream;
        this.copyStream = new ByteArrayOutputStream();
    }

    // Whenever the original stream is written to, also write it
    // to the copy
    @Override
    public void write(int data) throws IOException {
        this.origStream.write(data);
        this.copyStream.write(data);
    }

    // Other inherited methods that should be overridden
    @Override 
    public boolean isReady(){
        return this.origStream.isReady();
    }
    @Override 
    public void setWriteListener(WriteListener listener){
        this.origStream.setWriteListener(listener);
    }
    @Override 
    public void flush() throws IOException {
        this.origStream.flush();
    }

    // Include a method to get the data that was written to the stream
    public byte[] getByteArray() {
        return this.copyStream.toByteArray();
    }
}