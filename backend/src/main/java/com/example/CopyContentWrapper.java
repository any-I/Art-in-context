package com.example;

import jakarta.servlet.http.HttpServletResponseWrapper;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.ServletOutputStream;
import java.io.IOException;

public class CopyContentWrapper extends HttpServletResponseWrapper {
    private CopyOutputStream outStream;

    // When wrapper is constructed around response object, construct
    // outStream so that it copies the response's output stream
    public CopyContentWrapper(HttpServletResponse response) throws IOException {
        super(response);
    }

    // Ensure that the special output stream that can copy what
    // was written to the response is being used
    @Override
    public ServletOutputStream getOutputStream() throws IOException {
        if(this.outStream == null){
            this.outStream = new CopyOutputStream(super.getOutputStream());
        }
        return this.outStream;
    }

    // Have method to return the data that was written to the response
    public byte[] getContentAsByteArray(){
        return outStream.getByteArray();
    }
}