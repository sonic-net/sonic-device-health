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
 *  Human readable string matching error code.
 */
const char *get_last_error(int **errcode);

/*
 * Get the last error encountered.
 *
 * Input:
 *  errcode -- error code for which matching string is requested.
 *
 * Output:
 *  None
 *
 * Return:
 *  Human readable string matching error code.
 */
const char *get_error_str(int errcode)


/*
 * Register the plugin
 *
 * Input:
 *  plugin_name -- Name of the plugin
 *
 * Output:
 *  handle -- Handle returned upon successful registration
 *
 * Return:
 *  0 for success
 *  !=0 implies error
 */
int ClientRegister(const char *plugin_name, int **handle);


/*
 * Deregister the plugin
 *
 * Input:
 *  handle -- As returned from last registration.
 *
 * Output:
 *  None
 *
 * Return:
 *  None.
 *
 */
void ClientDeregister(int handle);

/*
 * Register an action
 *
 * Input:
 *  handle - Handle from plugin registration
 *  action_name -- Name of the action
 *
 * Output:
 *  None
 *
 * Return:
 *  0 for success
 *  !=0 implies error
 */
int ClientRegisterAction(int handle, const char *action_name);


/*
 * Deregister an action
 * To deregister all actions, deregister the plugin.
 *
 * Input:
 *  handle - Handle from plugin registration
 *  action_name -- Name of the action
 *
 * Output:
 *  None
 *
 * Return:
 *  0 for success
 *  !=0 implies error
 */
int ClientDeregisterAction(int handle, const char *action_name);


/*
 * Run anomaly action
 *
 * Input:
 *  handle - Handle from plugin registration
 *  action_name -- Name of the action
 *
 * Output:
 *  data - Action's o/p
 *
 * Return:
 *  0 for success
 *  !=0 implies error
 */
int RunAnomaly(int handle, const char *action_name, const char **data);


/*
 * Run non-anomaly action
 *
 * Input:
 *  handle - Handle from plugin registration
 *  action_name -- Name of the action
 *  ctx -- Context from previous actions as JSON string
 *         of following list object.
 *      [
 *          "<sequence>": {
 *              "<action name>": { <action's o/p> }
 *          },
 *          ...
 *      ]
 *
 * Output:
 *  data - Action's o/p
 *
 * Return:
 *  0 for success
 *  !=0 implies error
 */
int RunAnomaly(int handle, const char *action_name, const char **data);


