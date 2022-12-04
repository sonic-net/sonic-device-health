#ifndef _SERVER_H_
#define _SERVER_H_

/*
 * APIs in use by Server
 *
 * We provide C-binding to facilitate direct use by Go & Python.
 * We don't need to use SWIG to provide any Go/Python binding.
 */

#ifdef __cplusplus
extern "C" {
#endif
}

/***************************************************
 * Request from client to server                   *
 ***************************************************/
enum ClientRequestType {
    CL_REQ_REGISTER_CLIENT = 0,
    CLIENT_REQ_COUNT
};

/*
 * Request from client/plugin to server.
 */
typedef struct clientRequest {
    /* Type of request. Available request types are in enum */
    ClientRequestType type;

    /* Name of the plugin that raises this request. */
    const char *plugin_name;

    /*
     * JSON string of data associated with request
     * NOTE: This request is raised from internal lib provided. 
     *      The lib provide custom APIs as one per request type.
     *      The plugins may use the custom API offered.
     *
     *      The API will validate the args, construct the JSON object,
     *      convert to string and provide. 
     *      Hence additional validation is not done by server.
     *      Schema based validation could be done, if deemed necessary
     *
     *  REGISTER_CLIENT
     *      data:
     *          [
     *              "<action name>": {
     *                      "priority": < Action's relative Pri > 
     *              },
     *              ...
     *          ]
     */
    const char *data;

} clientRequest_t;


/*
 * Response to client/plugin from server.
 */
typedef struct clientResponse {
    /* Type from corresponding request. */
    ClientRequestType type;

    /* Name of the plugin that raised the request. */
    const char *plugin_name;

    /*
     * JSON string of data associated with response.
     * This is response from server, hence need no validation,
     * NOTE:
     *      The lib provide custom APIs as one per request type.
     *      The API will parse the string to appropriate o/p params
     *      and return code.
     *
     * REGISTER_CLIENT:
     *      data: Has no response data. Hence empty string.
     *
     */
    const char *data;

    /*
     * result_code:
     *  It is 0 for success. Any other value implies failure in
     *  processing the request.
     *
     * result_str: Human readable string for result_code
     */
    int result_code;
    const char *result_str;

} clientResponse_t;

/*
 * Write request from client
 * 
 * Input:
 *  request - Request from client.
 *  
 * Output:
 *  None
 *
 * Return:
 *  Error code, where 0 implies success.
 *
 */
int WriteClientRequest (clientRequest_t *request);


/*
 * Read request from client
 * 
 * Input:
 *  type - If non-null, specifies type of request to read.
 *         If specified it ignore/Drop any other request type.
 *  
 * Output:
 *  request - complete request
 *
 * Return:
 *  Error code, where 0 implies success.
 *
 */
int ReadClientRequest (
        ClientRequestType *type,
        clientRequest_t *request);


/*
 * Write response to client
 *
 * Input:
 *  response - Response to a request read.
 *
 * Output:
 *  None
 *
 * Return:
 *  0 for success. Any other implies failure.
 */
int WriteClientResponse (clientResponse_t response);


/*
 * Read response to client
 *
 * Input:
 *  type:
 *      Optional.
 *      If non null, only read response for given request type
 *
 *  plugin_name:
 *      Optional.
 *      If non null, only read response for given plugin-name.
 *
 * Output:
 *  response - Read response that matches given filter, if any.
 *
 * Return
 *  0 implies success. Any other non-zero value implies failure.
 *
 */
int ReadClientResponse (
        ClientRequestType *type,
        const char *plugin_name,
        clientResponse_t *response);


/****************************************************
 * Request from server to client                    *
 ****************************************************/

enum ServerRequestType {
    SER_REQ_INVOKE_ACTION = 0,
    SERVER_REQ_COUNT
};


/*
 * Request from server to client.
 */
typedef struct ServerRequest {
    /* Type of request. Available request types are in enum */
    ServerRequestType type;

    /* Name of the plugin that raises this request. */
    const char *plugin_name;

    /*
     * JSON string of data associated with request
     * NOTE:
     *      This request is raised by server. 
     *      Hence no data validation needed.
     *
     *      The lib provide custom APIs as one per request type.
     *      The client calls the custom APIs
     *      The lib code will internally call API to read server request.
     *      The API will parse the string into o/p params of tha custom API.
     *
     * REQUEST_ACTION
     *  data: 
     *  {
     *      "Action-name": "<Name of the action to invoke>",
     *      "context": [
     *          "<sequence>": {
     *              "<action name>": { <action's o/p> }
     *          },
     *          ...
     *      ]
     * }
     */
    const char *data;

} ServerRequest_t;

/*
 * Response to server from client.
 */
typedef struct ServerResponse {
    /* Type from corresponding request. */
    ServerRequestType type;

    /* Name of the plugin that raised the request. */
    const char *plugin_name;

    /*
     * JSON string of data associated with response.
     * This is response from the action, hence action specific.
     * NOTE:
     *      The lib provide custom APIs as one per request type.
     *      The lib will validate the i/p params and parse it into
     *      JSON string.
     *      Since lib provides the JSON string, no validation needed.
     *
     * REQUEST_ACTION
     *  data: 
     *  {
     *      "Action-name": "<Name of the action to invoke>",
     *      "action-data": <action's o/p as object per schema.>
     *  }
     */
    const char *data;

    /*
     * result_code:
     *  It is 0 for success. Any other value implies failure in
     *  processing the request.
     *
     * result_str: Human readable string for result_code
     */
    int result_code;
    const char *result_str;

} ServerResponse_t;

/*
 * Write request from Server to client
 * 
 * Input:
 *  request - Request from Server.
 *  
 * Output:
 *  None
 *
 * Return:
 *  Error code, where 0 implies success.
 *
 */
int WriteServerRequest (ServerRequest_t *request);


/*
 * Read request from Server to client
 * 
 * Input:
 *  type:
 *      Optional.
 *      If non null, only read request for given request type
 *
 *  plugin_name:
 *      Optional.
 *      If non null, only read request for given plugin-name.
 *
 * Output:
 *  request - Read request that matches given filter, if any.
 *
 * Return:
 *  Error code, where 0 implies success.
 *
 */
int ReadServerRequest (
        ServerRequestType *type,
        const char *plugin_name,
        ServerRequest_t *request);


/*
 * Write response to Server
 *
 * Input:
 *  response - Response to a request read.
 *
 * Output:
 *  None
 *
 * Return:
 *  0 for success. Any other implies failure.
 */
int WriteServerResponse (ServerResponse_t response);


/*
 * Read response to Server
 *
 * Input:
 *  type:
 *      Optional.
 *      If non null, only read response for given request type
 *
 * Output:
 *  response - Read response that matches given filter, if any.
 *
 * Return
 *  0 implies success. Any other non-zero value implies failure.
 *
 */
int ReadServerResponse (
        ServerRequestType *type,
        ServerResponse_t *response);


#endif
