# mascotd IPC protocol

Protocol version **0.1.0**. This is also the minimum version the overlay accepts.

mascotd listens on an `AF_UNIX` `SOCK_SEQPACKET` socket, by default
`$XDG_RUNTIME_DIR/mascotd.sock` (`-s` changes it). Each packet is one message. All integers are in
host byte order, and file descriptors are passed with `SCM_RIGHTS`. Clients must close the
descriptors they receive.

The overlay also has a separate, much simpler line-JSON socket for chat front-ends. See
[Chat socket](#chat-socket) at the end.

# Types

string - byte-prefixed char string, uint8 n + n * char (so at most 255 bytes, no terminating NUL)
variable - 9 bytes: uint8 KIND, float or uint32 value, bool used, bool evaluated once, uint16 script_id

# Header

8 bytes, followed by the payload:

| Field | Type | Description |
| ----- | ---- | ----------- |
| Type | uint8 | Type of the message |
| Flags | uint8 | Flags |
| Length | uint16 | Length of the whole message, **including** this header |
| Object ID | uint32 | ID of the object |

If object ID is 0, the message is a generic message.

The top byte of an object ID is the object's type, and the lower 24 bits are its index:

| Top byte | Object type |
| -------- | ----------- |
| 0 | none (generic) |
| 1 | environment |
| 2 | mascot |
| 3 | plugin |
| 4 | prototype |
| 5 | selection |
| 6 | import |
| 7 | export |
| 8 | shm_pool |
| 9 | buffer |
| 10 | popup |
| 11 | click_event |

The overlay looks up a request's handler from the object type and the message type, so a request
is only understood when it is sent on the right kind of object. Requests it does not know are
logged as unhandled and ignored.

# Versions

Versions are sent as uint64: 21 bits each for major, minor and patch (`major << 42 | minor << 21 |
patch`). 0.1.0 is `0x200000`. A client whose version is newer than the overlay's, or older than
its minimum, gets an ERROR notice `connector.error.version.too_new` or
`connector.error.version.too_old` (values: client version, server version, minimum version) and
is disconnected.

# Messages

Messages marked *not implemented* are reserved. The overlay does not handle these requests, and
it never sends these events.

| Packet ID | Packet Name | Packet Description | Direction |
| --------- | ----------- | ------------------ | --------- |
| 0x00 | Client Hello | Client Hello, sent as first packet | Serverbound |
| 0x01 | Server Hello | Sent as response to Client Hello, sent only if the client connection is accepted | Clientbound |
| 0x02 | Disconnect | Disconnection notice | Clientbound |
| 0x03 | Notice | Message, client is disconnected immediately if it's is a error | Clientbound |
| 0x04 | Start | Start session | Clientbound |
| 0x05 | environment() | Sent when new environment is added (or on before Start) | Clientbound |
| 0x06 | environment.changed() | Updates environment info | Clientbound |
| 0x07 | environment.mascot() | Adds a new mascot to the environment | Clientbound |
| 0x08 | environment.withdrawn() | Removes the environment | Clientbound |
| 0x09 | prototype() | Sent when new prototype is added (or on before Start) | Clientbound |
| 0x0A | prototype.name() | Sets name of prototype referred by Object ID | Clientbound |
| 0x0B | prototype.display_name() | Sets display name of prototype referred by Object ID | Clientbound |
| 0x0C | prototype.path() | Sets path of prototype referred by Object ID | Clientbound |
| 0x0D | prototype.fd() | Sets file descriptor pointing to prototype dir (O_PATH | O_DIRECTORY) | Clientbound |
| 0x0E | prototype.add_action() | Adds a new action to the prototype referred by Object ID | Clientbound |
| 0x0F | prototype.add_behavior() | Adds a new behavior to the prototype referred by Object ID | Clientbound |
| 0x10 | prototype.icon() | Sets icon of prototype referred by Object ID | Clientbound |
| 0x11 | prototype.author() | Sets author of prototype referred by Object ID | Clientbound |
| 0x12 | prototype.version() | Sets version of prototype referred by Object ID | Clientbound |
| 0x13 | Commit prototypes | Apply changes to prototypes (atomically) | Clientbound |
| 0x14 | mascot.migrated() | Migrates mascot to the new environment | Clientbound |
| 0x15 | mascot.disposed() | Disposes mascot | Clientbound |
| 0x16 | mascot->get_info() | Gets information about mascot | Serverbound |
| 0x17 | mascot.info() | Contains current state of the mascot | Clientbound |
| 0x18 | mascot.clicked() | Triggered on secondary button click on mascot, creates new Object of type click_event | Clientbound |
| 0x19 | plugin() | Announces new plugin | Clientbound |
| 0x1A | plugin.description() | Contains full description of the plugin | Clientbound |
| 0x1B | plugin.window() | Announces new plugin-managed window | Clientbound |
| 0x1C | plugin.unloaded() | Unloads plugin | Clientbound |
| 0x1D | Commit plugins | Apply changes to plugins (atomically) | Clientbound |
| 0x1E | Select | Initializes selection, creates new Object of type selection | Serverbound |
| 0x1F | selection.done() | Selection completed, contains information about the selected point | Clientbound |
| 0x20 | selection.cancel() | Selection cancelled, for example by explicit request or if another selection is started | Clientbound |
| 0x21 | Reload prototype | Reloads prototype by its path, if path is empty, reloads all prototypes | Serverbound |
| 0x22 | Import prototype | Imports prototype by file descriptor, creates new Object of type import | Serverbound |
| 0x23 | import.failed() | Import failed, can be sent if prototype with same name already exists, then import can be retried with replace flag, acts as destructor for object | Clientbound |
| 0x24 | import.started() | Import started | Clientbound |
| 0x25 | import.finished() | Import finished, acts as destructor for object | Clientbound |
| 0x26 | import.progress() | Import progress | Clientbound |
| 0x27 | Export | Exports prototype by its id, creates new Object of type export | Serverbound |
| 0x28 | export.failed() | Export failed, acts as destructor for object | Clientbound |
| 0x29 | export.finished() | Export finished, acts as destructor for object | Clientbound |
| 0x2A | Spawn | Summons mascot | Serverbound |
| 0x2B | Dispose | Disposes mascot referred by its id | Serverbound |
| 0x2E | environment->close() | Asks environment to close (sent on an environment object) | Serverbound |
| 0x2F | plugin->restore_windows() | Moves windows to center of screen if possible (generic message) | Serverbound |
| 0x3A | plugin->deactivate() | *Not implemented* | Serverbound |
| 0x3B | plugin->activate() | *Not implemented* | Serverbound |
| 0x3C | plugin.status() | *Not implemented* | Clientbound |
| 0x3D | selection->cancel() | Cancels selection | Serverbound |
| 0x3E | Share shm pool | *Not implemented*: Shares shared memory pool, creates new Object of type shm_pool | Serverbound |
| 0x3F | shm_pool->create_buffer() | *Not implemented*: Creates buffer in shared memory pool, returns new Object of type buffer | Serverbound |
| 0x40 | shm_pool.imported() | *Not implemented*: Server imported shared memory pool successfully | Clientbound |
| 0x41 | shm_pool.failed() | *Not implemented*: Server failed to import shared memory pool | Clientbound |
| 0x42 | shm_pool->destroy() | *Not implemented*: Destroys shared memory pool referenced by Object ID | Serverbound |
| 0x43 | buffer->destroy() | *Not implemented*: Destroys buffer referenced by Object ID | Serverbound |
| 0x44 | click_event->accept() | *Not implemented*: Opens popup menu at click position, creates new Object of type popup, acts as destructor for object | Serverbound |
| 0x46 | popup->child_popup() | *Not implemented*: Creates child popup menu at specified position, creates new Object of type popup | Serverbound |
| 0x47 | popup->attach() | *Not implemented*: Attaches buffer to popup and immediately renders it | Serverbound |
| 0x48 | popup.mapped() | *Not implemented*: Sent when popup is mapped | Clientbound |
| 0x49 | popup.wheel() | *Not implemented*: Sent when mouse wheel is scrolled within popup | Clientbound |
| 0x4A | popup.dismissed() | *Not implemented*: Sent when popup is dismissed, acts as destructor for object | Clientbound |
| 0x4B | popup.enter() | *Not implemented*: Sent when mouse enters popup | Clientbound |
| 0x4C | popup.leave() | *Not implemented*: Sent when mouse exits popup | Clientbound |
| 0x4D | popup.motion() | *Not implemented*: Sent when mouse moves within popup | Clientbound |
| 0x4E | popup.clicked() | *Not implemented*: Sent when mouse clicks popup | Clientbound |
| 0x4F | popup->dismiss() | *Not implemented*: Sent when popup is discarded, acts as destructor for object | Serverbound |
| 0x50 | Apply behavior | Applies behavior to mascot | Serverbound |
| 0x51 | Get config key | Gets config value by key | Serverbound |
| 0x52 | Set config key | Sets config value by key | Serverbound |
| 0x53 | List config keys | Lists all config keys | Serverbound |
| 0x54 | Config key | Sends config key along with value, sent if client calls get, set or list (sent for each key in that case), clients should expect new keys at any time | Clientbound |
| 0x55 | click_event.expired() | Sent when click event expires, for example if new click event is created or some client is accepted click event| Clientbound |
| 0x56 | Stop | Ask overlay to stop | Serverbound |
| 0x57 | prototype.withdrawn() | Sent when prototype is withdrawn, acts as destructor for object | Clientbound |
| 0x58 | popup.frame() | *Not implemented*: See frame callbacks in wayland | Clientbound |
| 0x59 | mascot.tapped() | Triggered on primary button press and release on mascot without dragging it | Clientbound |
| 0x5A | sync() | Ask the overlay to answer with sync.done() once earlier requests are handled | Serverbound |
| 0x5B | sync.done() | Answer to sync() | Clientbound |

# Client Hello - 0x00

Should be first message sent by client to server, is protocol violation to sent any other message before this one. If sent at any other time, event is ignored.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Version | uint64 | Version of protocol | See [Versions](#versions); currently 0.1.0 |

# Server Hello - 0x01

Should be first message sent by server to client, is protocol violation to sent any other message before this one. If sent at any other time, event is ignored.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Version | uint64 | Version of protocol | |

# Disconnect - 0x02

Sent by server when it decides to disconnect client, message doesn't contain any additional information.


# Notice - 0x03

Sent by server when it wants to notify client about something, can be anything starting from Informational messages, Warning messages to Error messages. All error messages are fatal and client will be disconnected without any further notice.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Severity | uint8 | Severity of notice | |
| Alert | uint8 | Used to signal GUI clients to show message as alert | |
| Message | string | Message to be displayed | Can be localized string such as "generic.some.kind.of.notice" |
| Values | uint8_t | Count of values that is used for formatting message | |
| Value | string[] | Values used for message formatting, its up to client how to use them | Can be localized string such as "generic.some.kind.of.notice" |

Severity:
 - 0x00 INFO - Informational message
 - 0x01 WARN - Warning message, sent during runtime errors or when something goes wrong on overlay
 - 0x02 ERROR - Error message, fatal errors, For example sent if proxy initialization failed


# Start - 0x04

Notices that initialization is complete and client is knows enough to communicate with server.

This message contains no additional information.


# environment() - 0x05

Environment announcement. Sent when new display is added, contains information about new display

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Id | uint32 | ID of new environment Object | Should be treated as opaque ID |
| Name | string | Name of display | IF AVAILABLE |
| Description | string | Description of display | IF AVAILABLE |
| Compositor X | uint32 | X coordinate in compositor space | |
| Compositor Y | uint32 | Y coordinate in compositor space | |
| Width | uint32 | Logical width of the display | |
| Height | uint32 | Logical height of the display | |
| Scale | float | Logical scale of the display | |

# environment.changed() - 0x06

Environment properties changed. Sent when display properties changed, contains information about new display properties

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Name | string | Name of display | IF AVAILABLE |
| Description | string | Description of display | IF AVAILABLE |
| Compositor X | uint32 | X coordinate in compositor space | |
| Compositor Y | uint32 | Y coordinate in compositor space | |
| Width | uint32 | Logical width of the display | |
| Height | uint32 | Logical height of the display | |
| Scale | float | Logical scale of the display | |

# environment.mascot() - 0x07

Mascot created inside environment.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| ID | uint32 | Object ID of the new mascot | Should be treated as opaque ID |
| Prototype id | uint32 | Object ID of the prototype | Should be treated as opaque ID |

# environment.withdrawn() - 0x08

Environment withdrawn. Sent when environment is destroyed, for example when display is removed or by explicit request from client

Object ID is used to identify environment that was withdrawn.
If some mascots are present, they will be migrated to another environment or destroyed before that packet.

# prototype() - 0x09

Announcement of new mascot prototype. When received, prototype should not be used until it's commited by **Commit prototypes** packet

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| ID | uint32 | Object ID of the new mascot prototype | Should be treated as opaque ID |

# prototype.name() - 0x0A

Name of the mascot prototype. Sent when prototype is created or name is changed

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Name | string | Name of the prototype | |

# prototype.display_name() - 0x0B

Name of the mascot prototype's display. Sent when prototype is created or display name is changed

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Name | string | Name of the prototype's display | |

# prototype.path() - 0x0C

Relative path of the mascot, where full path known only to overlay.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Path | string | Relative path of the mascot | |

# prototype.fd() - 0x0D

File descriptor that points to the mascot prototype dir. Opened with O_DIRECTORY | O_RDONLY | O_PATH flags.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| FD | SCM_RIGHTS | File descriptor of the prototype | |

# prototype.add_action() - 0x0E

Add action name to the mascot prototype. Exposes action names available in the prototype.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Action | string | Action name | |
| Type | uint32 | Type of the action | |
| Embedded type | uint32 | Type of the embedded action | |
| Border type | uint32 | Type of the border used for the action | |

# prototype.add_behavior() - 0x0F

Add behavior name to the mascot prototype. Exposes behavior names available in the prototype.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Behavior | string | Behavior name | |
| Condition | uint8 | If behavior is condition container | |
| Hidden | uint8 | If behavior should be hidden from user | |
| Frequency | uint64 | Frequency of the behavior | |

# prototype.icon() - 0x10

Relative path from fd to sprite that should be used as icon.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Icon | string | Relative path to the icon sprite | |

# prototype.author() - 0x11

Name of the author of the mascot. Only sent if the prototype's manifest sets `artist`.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Author | string | Name of the author | |

# prototype.version() - 0x12

Version of the prototype's format, from the manifest's `version` (encoded as in
[Versions](#versions)). The overlay currently accepts only 0.0.1.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Version | uint64 | Format version of the prototype | |

# Commit prototypes - 0x13

Commit added/removed prototypes. Client should add new prototypes to it's list of known prototypes.
This packet has no payload.

# mascot.migrated() - 0x14

Mascot migrates from one environment to another. Can be caused by movement, dropping or if parent environment is withdrawn.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Environment | uint32 | Object ID of new environment | |

# mascot.disposed() - 0x15

Mascot is disposed. Sent when mascot is **fully** disposed, that means even if dispose animation is available and dispose animations are enabled, it will be sent once mascot is removed.

Object ID is used as argument.

# mascot->get_info() - 0x16

Ask server to provide information about mascot. If mascot is not exists, server will issue a warning.
It's not guaranteed when server will provide information about mascot. Its recommended to call this method before any manipulations with mascot, as transformations are not reported to clients.

Object ID is used as argument.

# mascot.info() - 0x17

Server sents information about mascot. Mascot that receives that information is reffered by Object ID

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Prototype ID | uint32 | Object ID of the prototype | |
| Environment ID | uint32 | Object ID of the environment | |
| Current state | uint32 | Current state of mascot | |
| Current action name | string | Name of current action | |
| Current action index | uint32 | Index of current action | |
| Current behavior name | string | Name of current behavior | |
| Current affordance | string | Name of current affordance | |
| Actions stack depth | uint16 | Number of actions in stack | Can be used in debug purposes |
| Actions | tuple<string, uint32>[] | List of pairs of string and uint32, representing action name and action index | |
| Behavior pool size | uint32 | Number of behaviors in pool | |
| Behavior pool | tuple<string, uint64>[] | List of pairs of string and uint64, representing behavior name and it's frequency| |
| Variables count | uint8 | Number of variables in mascot | Currently hardcoded to 128, however not all of them are used |
| Variables | variable[] | List of variables | Refer to types section for actual variable type reference |


# mascot.clicked() - 0x18

Sent when user clicks on mascot using secondary mouse button. Creates new click_event Object ID and revokes previous one (if not currently in use)

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Object ID | uint32 | Object ID of the new click_event | |


# mascot.tapped() - 0x59

Sent to all clients when user presses and releases primary mouse button on mascot without moving the pointer far enough to start dragging it. Object ID in header refers to the mascot. Added in protocol version 0.1.0.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Environment ID | uint32 | Object ID of the environment the mascot is in | |
| X | uint32 | Pointer X position at release | Environment coordinates |
| Y | uint32 | Pointer Y position at release | Environment coordinates, bottom-referenced like mascot Y |

# sync() - 0x5A

No fields. The overlay handles a client's requests in order and answers with sync.done(), so once
that arrives, every notice caused by earlier requests has been sent. Requests that finish later on
their own (import, export) are not covered. Older overlays do not know this request: wait with a
timeout. Added after protocol version 0.1.0, without a version change.

# sync.done() - 0x5B

No fields. Answer to sync(); object ID is 0.


TODO:
# plugin() - 0x19 | Announce new plugin
# plugin.description() - 0x1A | Reports plugin description
# plugin.window() - 0x1B | Announce new window managed by plugin
# plugin.unloaded() - 0x1C | Reports plugin unload
# Commit plugin - 0x1D | Informs client about end of plugin changes

# Select - 0x1E

Initializes selection operation, creates new selection object and cancels any unfinished old selection objects

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Object ID | uint32 | Object ID of the new selection to be created | |
| Environments count | uint8 | Number of participating environments in selection | |
| Environments | uint32[] | List of environments IDs in selection | |


# selection.done() - 0x1F

User selected spot on the screen

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Environment ID | uint32 | Environment ID where selection was done | |
| Mascot ID | uint32 | ID of the selected mascot | |
| X | uint32 | X coordinate of the selected spot | |
| Y | uint32 | Y coordinate of the selected spot | |
| Surface local X | uint32 | X coordinate of the selected spot relative to the surface | Only makes sense when Mascot ID is not 0 |
| Surface local Y | uint32 | Y coordinate of the selected spot relative to the surface | Only makes sense when Mascot ID is not 0 |

# selection.cancel() - 0x20

User canceled selection operation. Object ID field in header used to identify selection to be canceled

# Reload prototype - 0x21

Reload prototype referenced by name or reload all prototypes if name was empty. Server will respond with Notice or Warning to that message.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Path | string | Path of the prototype to be reloaded | Empty string means reload all prototypes. Path is an relative path to the prototypes storage root |

# Import prototype - 0x22

Start import operation of prototype from file. File descriptor should point to either directory that overlay will be able to open or zipfile. Insides in all cases should be in .wlshm mascot format.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Object ID | uint32 | ID that will be created for import Object | |
| FD | SCM_RIGHTS | File descriptor pointing to the file descriptor of the prototype | |

Flags from header is used here
0x01 is treated as REPLACE flag, in case if prototype already exists

# import.failed() - 0x23

Import operation is failed. Object ID referenced in header will be destroyed.
Explaination will be sent in Notice Warning with Alert = 1 right after that message.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Error | uint32 | Error message code | |

Error:
  - 0: Unknown error
  - 1: Invalid file format
  - 2: Invalid mascot version
  - 3: Referenced mascot name already exists and REPLACE is not set, Alert in Notice is set to 0 in that case
  - 4: File is not a valid tar file
  - 5: Mascot version is not supported
  - 6: File is not file
  - 7: File is not opened in right mode (Expected read or readwrite)

# import.started() - 0x24

Informs client that import is started for Object ID referenced in header.

# import.finished() - 0x25

Import is successful. Object ID referenced in header will be destroyed.
It is recommended to reload prototype after import.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Relative path | string | Relative path to the imported prototype | |

# import.progress() - 0x26

Informs client about progress of import operation. Take into account that this message may be never sent, in that case GUI clients may want to show progress bar with indefinite progress or not at all.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Progress | float | Progress percentage | 0.0 - 1.0 |

# Export - 0x27

Export prototype referenced by Object ID to fd. Packet will create new export Object of type export.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| FD | SCM_RIGHTS | File descriptor opened in WRITE mode | |
| Object ID | uint32 | New ID for export Object | |
| Prototype ID | uint32 | ID of prototype to export | |

# export.failed() - 0x28

Export operation is failed. Object ID referenced in header will be destroyed.
Explaination will be sent in Notice Warning with Alert = 1 right after that message.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Error | uint32 | Error message code | |

Error:
  - 0: Unknown error
  - 1: FD is not valid
  - 2: FD not opened in WRITE mode
  - 3: Referenced prototype ID is not valid
  - 4: Server errored
  - 5: Cannot dup FD
  - 6: Prototype is unavailable

# export.finished() - 0x29

Export operation is successful. Object ID referenced in header will be destroyed.

# Spawn - 0x2A

Spawn mascot by prototype ID. Any errors reported via Notice Warning with Alert = 1.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Prototype ID | uint32 | ID of prototype to spawn | |
| Environment ID | uint32 | ID of environment to spawn in | |
| X | uint32 | X coordinate | |
| Y | uint32 | Y coordinate | |
| Spawn behavior | string | Spawn behavior | Can be empty for default behavior |

# mascot->dismiss() - 0x2B

Dispose mascot by Object ID. Will cause dispose event on overlay, but if mascot has dispose animation and dispose animations are enabled, there's no guarantee that the mascot will be disposed immediately.
Any errors reported via Notice Warning with Alert = 1.

Object ID referenced in header used as mascot ID.

# environment->close() - 0x2E

Suggest environment to close. Acts same as display disconnect. NOTICE: If environment is closed, it not possible to later reopen it, only possible workaround is to reconnect display.

Object ID referenced in header used as environment ID.

Any errors reported via Notice Warning with Alert = 1.

# plugin->restore_windows() - 0x2F

Generic message (object ID 0) without payload. Asks the loaded plugins to move their windows back
on screen.

TODO:
plugin->deactivate()
plugin->activate()
plugin.status()


# selection->cancel() - 0x3D

Cancel selection **caused by client**.

Object ID referenced in header used as selection ID.

Any errors reported via Notice Warning with Alert = 1.

# Popup API (not implemented)

The messages from 0x3E to 0x4F and 0x58 are a sketch of a popup-menu API and **do not work**.
The overlay does not register handlers for the requests (0x3E, 0x3F, 0x42, 0x43, 0x44, 0x46,
0x47, 0x4F), so they are logged as unhandled and ignored. It never sends 0x48, 0x49, 0x4B to 0x4E
or 0x58. A popup would also have no keyboard input. `mascot.clicked()` (0x18) and
`click_event.expired()` (0x55) are sent, but a click event cannot be accepted. The descriptions
below are kept as a reference for the design only.

## Share shm pool - 0x3E

Shares shared memory pool, creates new Object of type shm_pool.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| FD | SCM_RIGHTS | File descriptor of shared memory pool | Requires MMAP_SHARED |
| New Object ID | uint32 | New Object ID of shared memory pool | |
| Size | uint32 | Size of shared memory pool | |

## shm_pool->create_buffer() - 0x3F

Create new buffer from shared memory pool

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| New Object ID | uint32 | New Object ID of buffer | |
| Offset | uint32 | Offset of buffer in shared memory pool | |
| Width | uint32 | Width of buffer | |
| Height | uint32 | Height of buffer | |
| Stride | uint32 | Stride of buffer | |
| Format | uint32 | Wayland-specific format of buffer | Recommended to use `WL_SHM_FORMAT_ARGB8888` or `WL_SHM_FORMAT_XRGB8888` |

## shm_pool.imported() - 0x40

Marks pool as successfully imported.

## shm_pool.failed() - 0x41

Marks pool as failed to import.
No additional information provided.
Acts as destructor for Object

## shm_pool->destroy() - 0x42

Destroy shared memory pool.
Object ID referenced in header used as shm_pool ID.

## buffer->destroy() - 0x43

Destroy buffer.
Object ID referenced in header used as buffer ID.

## click_event->accept() - 0x44

Accepts click event and immediately creates a new Popup Object.
All other clients will receive a `click_event.expired()` event.
If called on expired id, overlay will send `popup.dismissed()` event immediately.

Object ID from header used as click_event ID.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Popup ID | uint32 | ID of created popup | |
| Width | uint32 | Width of popup | |
| Height | uint32 | Height of popup | |

## popup->child_popup() - 0x46

Creates a new child popup.
Object ID from header used as parent Popup ID.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Popup ID | uint32 | ID of created popup | |
| Width | uint32 | Width of popup | |
| Height | uint32 | Height of popup | |
| X | uint32 | X of popup | Surface local coordinates of the parent |
| Y | uint32 | Y of popup | Surface local coordinates of the parent |

## popup->attach() - 0x47

Attaches buffer to the popup.
Object ID from header used as popup ID.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Buffer ID | uint32 | ID of buffer to attach | |
| X Damage | uint32 | X of damage rectangle | Surface local coordinates |
| Y Damage | uint32 | Y of damage rectangle | Surface local coordinates |
| Width Damage | uint32 | Width of damage rectangle | Surface local coordinates |
| Height Damage | uint32 | Height of damage rectangle | Surface local coordinates |

## popup.mapped() - 0x48

Sent when popup is mapped.

Object ID from header used as popup ID.

## popup.wheel() - 0x49

Sent when mouse wheel is scrolled within popup.

Object ID from header used as popup ID.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Delta | int32 | Scroll delta | |

## popup.dismissed() - 0x4A

Sent when popup is dismissed.

Object ID from header used as popup ID.

## popup.enter() - 0x4B

Sent when popup is entered.

Object ID from header used as popup ID.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| X | uint32 | X location of pointer | Surface local coordinates |
| Y | uint32 | Y location of pointer | Surface local coordinates |

## popup.leave() - 0x4C

Sent when popup is left.

Object ID from header used as popup ID.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| X | uint32 | X location of pointer | Surface local coordinates |
| Y | uint32 | Y location of pointer | Surface local coordinates |

## popup.motion() - 0x4D

Sent when popup is moved.

Object ID from header used as popup ID.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| X | uint32 | X location of pointer | Surface local coordinates |
| Y | uint32 | Y location of pointer | Surface local coordinates |

## popup.clicked() - 0x4E

Sent when popup is clicked.

Object ID from header used as popup ID.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| X | uint32 | X location of pointer | Surface local coordinates |
| Y | uint32 | Y location of pointer | Surface local coordinates |
| Button | uint32 | Button that was clicked | linux input keycode |

## popup->dismiss() - 0x4F

Dismiss popup.
Will dismiss all child popups as well.

Object ID from header used as popup ID.

## popup.frame() - 0x58

Same as frame callbacks in
wayland, but client doesn't requests it explicitly.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Time | uint32 | Time in unspecified clock | |

# Apply behavior - 0x50

Apply behavior by name to mascot referenced by Object ID. Will cause apply behavior event on overlay.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Behavior | string | Behavior to apply | |

# Get config key - 0x51

Schedules callback to get config key value.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Key | string | Config key to get value for | |

# Set config key - 0x52

Sets config key value, schedules callback to get updated value

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Key | string | Config key to set value for | |
| Value | string | Value to set | Will be converted on server to appropriate type |

# List config keys - 0x53

Lists all config keys.


# Config key - 0x54

Get config key value.

| Field | Type | Description | Note |
|-------|------|-------------|-------|
| Key | string | Config key to get value for | |
| Value | string | Value to get | Note: Client should present values as appropriate types |

# click_event.expired() - 0x55

Sent when click event is invalidated by any cause.

Object ID referenced in header used as click event ID.

# Stop - 0x56

Ask overlay to stop.

# prototype.withdrawn() - 0x57

Sent when prototype is withdrawn, acts as destructor for object.

# Chat socket

Besides the binary protocol, mascotd listens on a plain `SOCK_STREAM` Unix socket for chat
front-ends such as the bundled speech bubble. Its path is derived from the IPC socket: `foo.sock`
becomes `foo-chat.sock`, and any other name gets `-chat` appended. By default that is
`$XDG_RUNTIME_DIR/mascotd-chat.sock`. Several clients may be connected at once.

Each message, in both directions, is one JSON object on one line ending with `\n`. Send **compact**
JSON (`{"event":"close","mascot":3}`): the overlay recognises an event by the exact text
`"event":"<name>"`, without whitespace. Lines longer than 511 bytes are dropped.

All coordinates are in logical pixels, local to the mascot's environment (output), with **y
measured from the top**. This differs from the binary protocol, where mascot y is
bottom-referenced.

When the `chat_enabled` setting is false, the overlay sends no `tap` events and disconnects every
chat client, but keeps listening, so clients can reconnect once it is turned on again.

## Overlay to client

### tap

Sent to every client when a mascot is tapped (primary button pressed and released without dragging).
If at least one client received it, the mascot is *held*: it sits down (behaviour `SitDown`) and
keeps sitting until the client sends `close`, the mascot is dragged, or the last chat client
disconnects. Only one mascot is held at a time. A double click gives two `tap` events.

```json
{"event":"tap","mascot":1,"prototype":"Shimeji","output":"DP-1",
 "pointer":{"x":285,"y":1403},"anchor":{"x":285,"y":1440},"looking_right":true,
 "sprite":{"x":220,"y":1312,"width":128,"height":128},
 "surface":{"width":2560,"height":1440},"command":null,"role":null,"memory":8000,
 "tools":"time,weather","dotfiles":null,"prompt":null,"language":null,
 "version":"0.4.0"}
```

| Field | Type | Description |
|-------|------|-------------|
| mascot | number | Mascot ID (the lower 24 bits of its object ID) |
| prototype | string | Display name of the mascot's prototype, or its name if it has none |
| output | string | Name of the output the mascot is on |
| pointer | {x, y} | Pointer position at release |
| anchor | {x, y} | The mascot's anchor point (where its feet are) |
| looking_right | bool | Which way the mascot faces |
| sprite | {x, y, width, height} or null | The box the current sprite is drawn in; null if it has no pose yet |
| surface | {width, height} | Size of the overlay's surface on that output |
| command | string or null | The `chat_command` setting, or null if it is empty. The overlay does not run it |
| memory | number | The `chat_memory` setting: about how many tokens a mascot's memory may hold before the bubble sums it up; 0 = never |
| remark | true, or absent | Present on a remark (`chat_remarks`): the mascot says something on its own, so the bubble should not take the keyboard. The mascot is held as for a tap |
| role | string or null | The role the bubble starts with for this mascot: its entry in `chat_roles`, else the `chat_role` setting; null if neither is set or its entry is empty |
| tools | string or null | The `chat_tools` setting: the bubble's tools, comma-separated; null if it is empty |
| dotfiles | string or null | The `chat_dotfiles` setting: the hidden files and directories the file tools may see, `;`-separated; null if it is empty |
| language | string or null | The `chat_language` setting (e.g. `Danish`): the user's language; null if it is empty |
| prompt | string or null | The prototype's own system prompt (a `prompt.md` in its directory, at most 4 KiB, e.g. Robo's personality); null if it has none. The bubble uses it unless a role is chosen |
| version | string | The running overlay's version (`mascotd --version`); the bubble shows it in `.info` |

### menu

Sent to every client when a mascot is right-clicked (and has no hotspot there); the bubble shows a
menu at the pointer. The same fields as `tap`, but `"event":"menu"` and no `remark`; the mascot is
held as for a tap, until the client sends `close` (when the menu closes, unless it opened the bubble
at the mascot). Also:

| Field | Type | Description |
|-------|------|-------------|
| asleep | bool | Whether this mascot is asleep (`sleep`, a middle click) |
| all_asleep | bool | Whether a `sleep` without `mascot` holds (e.g. from hypridle, or with `minutes`) |
| staying | bool | Whether this mascot stays where it is (`stay`, the menu's Stay) |

### dragged

`{"event":"dragged","mascot":N}`: the user started dragging mascot N. The mascot is no longer
held; a client showing a conversation for it will usually hide it, and close it on `dropped`.

### dropped

`{"event":"dropped","mascot":N}`: the button went up after dragging mascot N, however the drag
ended. A window that unmaps while the button is still down makes Hyprland send the daemon a
false release (the drag ends at once), so close windows here rather than on `dragged`.

### egg

`{"event":"egg","mascot":N}`: mascot N was tapped quickly many times (6 within 3 seconds) and plays
its `EasterEgg` behaviour instead of that tap. It is no longer held: close the bubble at it. Only sent
when the prototype has an `EasterEgg` behaviour and the mascot is on the floor; otherwise that tap is
a `tap` like the others. While it plays, taps on that mascot send nothing (they would end it).

### prototypes

`{"event":"prototypes","names":["Shimeji","Example"]}`: answer to `list`, sent only to the
client that asked. Lists the display names of all loaded prototypes.

### swapped

`{"event":"swapped","mascot":N,"to":M,"prototype":"Example","role":null}`: answer to `swap`, sent to every
client. Mascot N has been replaced by mascot M, of the named prototype. If N was held, M is now
held instead. `role` is the new mascot's role, as in `tap`.

### swap_failed

`{"event":"swap_failed","mascot":N,"reason":"..."}`: sent only to the client whose `swap` failed.
`reason` is a human-readable English sentence.

## Client to overlay

| Message | Effect |
|---------|--------|
| `{"event":"close","mascot":N}` | The conversation with mascot N is over; it is no longer held |
| `{"event":"hold","mascot":N}` | Hold mascot N again, as a `tap` would (it sits down, at once on the floor, else when it lands), unless it is asleep. Dragging a mascot lets go of it: the bubble sends this when one that waits with its answer (`answered`) is dropped, then `talking` or `answered` again |
| `{"event":"talking","mascot":N,"active":true}` | While `active` is true, the held mascot N plays its `Talk` behaviour (if the prototype defines one; otherwise it keeps sitting). Send `false` when the answer is complete |
| `{"event":"doing","mascot":N,"tool":"todo"}` | A tool runs for the answer of the held mascot N; `tool` is its kind (the bubble's icon name: `todo`, `file`, `weather`…). For a kind the daemon knows the mascot plays the prototype's behaviour for it instead of `Talk`, if it has one: `todo` → `Todo`, `reminder` → `Reminder`, `weather` → `Weather`, `folder` and `file` → `Files`, `search` → `Search`, `image` → `Image`, `shell` → `Shell`, `sleep` → `Sleepy`, `system` → `System`, `machine` → `Machine`; `unsure` → `Unsure` (sent when the answer starts, after the system tools found nothing to go on); `done` → `Done` (sent when the answer starts, after `remove_todo` took an item off the todo list, or when `.todo done` did); `failed` → `Failed` (sent when the answer failed); and `alarm` → `Alarm` (not a tool: a reminder that is due is shown). `"tool":""` when the answer starts: back to `Talk` (or `SitDown` when it is not answering) |
| `{"event":"answered","mascot":N}` | The held mascot N repeats its `Answered` behaviour (otherwise it sits) until the next `tap` holds it again: an answer waits to be read. The bubble sends it when it was closed while answering, without `close`, so the mascot stays |
| `{"event":"stay","mascot":N,"active":true}` | Mascot N stays where it is, awake (the menu's Stay): it sits, then does what its figure can do on the spot, wherever it is dropped, until `false` |
| `{"event":"list"}` | Ask for the loaded prototypes, answered with `prototypes` |
| `{"event":"swap","mascot":N,"prototype":"name"}` | Replace mascot N with a new mascot of the named prototype, at the same position and facing the same way. The name is matched against display and internal names, ignoring case. Answered with `swapped` or `swap_failed` |
| `{"event":"toggle"}` | Sent by `mascot chat`. Passed on unchanged to every other client: the bubble closes, or asks to open with `open` |
| `{"event":"menu_toggle"}` | Sent by `mascot menu`. Passed on unchanged to every other client: the bubble closes its menu, or asks for one with `menu` |
| `{"event":"menu","mascot":N}` | Open the menu at mascot N, or at the first mascot if N is -1 or gone: answered with a `menu` event to every client, as if the mascot had been right-clicked with the pointer at the top of its sprite, and the mascot is held |
| `{"event":"remark"}`, `{"event":"remark","mascot":N}` | A random mascot (or mascot N, if it is still there) says something now, as the `chat_remarks` setting does every N to 2N minutes: a `tap` event with `"remark":true`. Ignored while a mascot is held (the bubble is open), or when the mascot is not on the floor (falling or dragged). Never a mascot that is asleep (`sleep`): mascot N asleep, a random awake one says it. The bubble sends it with the mascot talked to last to show a due reminder |
| `{"event":"open","mascot":N}` | Open the bubble at mascot N, or at the first mascot if N is -1 or gone: answered with a `tap` event to every client, as if the mascot had been tapped with the pointer at its anchor, and the mascot is held |
| `{"event":"sleep","mascot":N}`, `{"event":"wake","mascot":N}` | Put only mascot N to sleep, or wake it up, as a middle click does (the menu) |
| `{"event":"dismiss","mascot":N}` | Send mascot N away, with its dismiss animation if `allow_dismiss_animations` is on (the menu). If it was the last mascot, the overlay stops |
| `{"event":"sleep"}`, `{"event":"wake"}` | Sent by `mascot sleep`/`mascot wake`. With `"minutes":N` (`mascot sleep --minutes`, the `sleep_mode` tool) they sleep N minutes; a `wake` without `"all":true` does not end that early. Every mascot (also those summoned later) repeats its `Asleep`, `Sleep`, `LieDown` or `SitDown` behaviour, whichever the prototype has first, on the floor and not while held; `wake` lets them pick behaviours as usual again. A mascot asleep never says anything: `remark` picks an awake one, or is ignored if none is |

Other messages are ignored. Older clients sent `hiding` and `hidden` around unmapping their
window; they are no longer needed.

A prototype opts into talking by defining a behaviour named `Talk` with frequency 0 (so it is
never picked at random) that refers to an existing action.
