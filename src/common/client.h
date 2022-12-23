#ifndef _CLIENT_H_
#define _CLIENT_H_

/*
 * APIs in use by Server
 *
 * We provide C-binding to facilitate direct use by Go & Python.
 * We don't need to use SWIG to provide any Go/Python binding.
 */

#ifdef __cplusplus
extern "C" {
#endif

/***************************************************
 * Request from client to server                   *
 ***************************************************/
enum ClientRequestType {
    CL_REQ_REGISTER_CLIENT = 0,
    CLIENT_REQ_COUNT
};

/*
 * Requests used by clients/plugins to reach server.
 *
 * The lib would use APIs from server.h to reach the server.
 * The custom APIs here makes it easier for clients use and
 * as well validate all the API specific args.
 *
 */

/*
 * Get the last error encountered.
 *
 * Input:
 *  None
 *
 * Output:
 *  errcode -- Last returned error code.
 *
 * Return:
 *  last encountered error code
 */
int get_last_error();


/*
 * Get the last error encountered as string.
 *
 * Input:
 *  None
 *
 * Output:
 *  None
 *
 * Return:
 *  Human readable string matching error code.
 */
const char *get_error_str();

/*
 * Register the plugin process
 *
 * A process could register multiple actions.
 * A process restart is guaranteed to use the same ID,
 * which can help engine clean old registrations and start new.
 *
 * Input:
 *  plugin_proc_id -- Name of the plugin process ID
 *      A process reuses this ID upon restart.
 *      Engine identifies actions against this ID
 *      to block any duplicate registrations from
 *      different processes.
 *
 * Output:
 *  None
 *
 * Return:
 *  0 for success
 *  !=0 implies error
 */
int register_client(const char *plugin_proc_id);

/*
 * Register the plugins 
 *
 * Expect this process ID is pre-registered.
 *
 * Input:
 *  action -- Name of the action.
 *
 * Output:
 *  None
 *
 * Return:
 *  0 for success
 *  !=0 implies error
 */
int register_plugin(const char *action);


/*
 * Deregister the plugin
 *
 * Input:
 *  plugin_proc_id - Id used during registration.
 *
 * Output:
 *  None
 *
 * Return:
 *  None.
 *
 */
void deregister_client(const char *plugin_proc_id);


/*
 * Heartbeat touch
 *
 * Calls heartbeat touch upon hesartbeat touch from a plugin
 *
 * Input:
 *  action_name - Name of the action of this plugin making the callback.
 *
 *  instance-id - ID given in corresponding request.
 *
 * Output:
 *  None
 *
 * Return:
 *  None
 */
void touch_heartbeat(const char *action, const char *instance_id);


#if 0

    DROP START

struct action_request {
    /* Name of the action being requested */
    const char *action_name;

    /*
     * Instance ID assigned for this call,
     * Log messages may include this ID to identify it with
     * runtime instance ID.
     */
    const char *instance_id;

    /*
     * JSON string of all data spewed from preceding actions
     *
     * {
     *      <sequence>: <JSON string of returned action-data>[, ...]
     * }
     */
    const char *context;
};

struct action_response {
    const char *action_name;

    /*
     * Instance ID assigned for the corresponding request.
     */
    const char *instance_id;

    /*
     * JSON string of action data spewed by this action.
     */
    const char *action_data;

    /*
     * Result code of the action completion.
     */
    int result_code;

    /*
     * Result string of the action completion.
     */
    int result_str;
};

int read_action_request(action_request *req);
int write_action_response(action_response *res);

    DROP END

#endif


/*
 * Read Action request
 * Json string
 * {
 *      "request_type": "<action/shutdown/...>"
 *      "action_name": "<Name>",
 *      "instance_id": "<id>",
 *      "context": "<JSON string of context>",
 *      "timeout" : <TImeout for the request>
 *  }
 *  context -- JSON string of
 *  [
 *      { <action name> : <action data per schema> }
 *      ...
 *  ]
 *  Order in list matches order of invocation
 *
 * Input:
 *  None
 *
 * Output:
 *
 * Return
 *  Empty string on error / timeout.
 *  Use get_last_error() for err code
 *      0 for sucess or timeout
 *      !=0 implies failure
 */
const char *read_action_request();


/*
 * Write Action response
 *
 * Input:
 *  res - response being returned.
 * Json string
 * {
 *      "request_type": "<action/shutdown/...>"
 *      "action_name"   : "<Name>",
 *      "instance_id"   : "<id>",
 *      "action_data"   : "data as spewed by action as result",
 *      "result_code"   : <Result code of peocessing the request>
 *      "result_code"   : <Result code of peocessing the request>
 *      "result_str"    : <Human readabloe string of result code >
 *  }
 *  "action_data" -- JSON string as per action schema devoid of common
 *          attributes
 *
 * Output:
 *  None
 *
 * Return
 *  0 for sucess
 *  !=0 implies failure
 */
int write_action_response(const char *res);


/*
 *  Poll for request from server/engine anjd as well
 *  listen for data from any of the fds provided
 *
 * Input:
 *  lst_fds: list of fds to listen for data
 *  cnt: Count of fds in list.
 *  timeout: Count of seconds to wait before calling time out.
 *      0 - Check and return immediately
 *     -1 - Block until data arrives on any one/more.
 *     >0 - Count of seconds to wait.
 *
 * Output:
 *  None
 *
 * Return:
 *  -2 - Timeout
 *  -1 - Message from server/engine
 *  >= 0 -- Fd that has message
 *  <other values> -- undefined.
 */
int poll_for_data(int *lst_fds, int cnt, int timeout);



#ifdef __cplusplus
}
#endif

#endif // _CLIENT_H_
