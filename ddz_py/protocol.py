'''
| body length | body (json) |
|      4B     |             |

Messages are serialized into json. The message object must have a property
named 'type' which indicates the type of the message. There're serveral message
types:

{
  "type": "tell",
  "content": "..."
}

Type 'tell' (s2c): The server wants to send a server-written message to client,
content read from property 'content', encoded utf-8.

{
  "type": "sync",
  "attr": [
    {
      "key": "...",
      "val": "..."
    },
    ...
  ]
}

Type 'sync' (s2c): Client need to make its data as same as the property 'attr', which
is a list of key-value pair. Note that val may be str, list[str], or bool, etc.

{
  "type": "join",
  "name": "..."
}

Type 'join' (c2s): Client should send this message as the first message when joining
the server. Property name is the name of the client, encoded utf-8.

{
  "type": "chat",
  "content": "..."
}

Type 'chat' (c2s): Client send this type of message to server when chatting,
then server should broadcast the message using the following type.

{
  "type": "chat",
  "author": "...",
  "content": "..."
}

Type 'chat' (s2c): Server broadcasting the message authored by some client,
with property 'author' containing the name of the message author.

{
  "type": "play",
  "cards": "..."
}

Type 'play' (c2s): Client plays cards, then server should broadcast the message
using the following type.

{
  "type": "play",
  "player": "...",
  "cards": "..."
}

Type 'play' (s2c): Server broadcasting the message that some player played some
cards, property 'player' contains the player who plays the card.

{
  "type": "rating_update",
  "k": ..., // float, rating factor
  "delta": [
    {
      "name": "...", // str, name of the player
      "delta": ...,  // float, delta
      "rating": ..., // float, current rating
    }
  ]
}

Type 'rating_update' (s2c): Server send this type of message when a rated game
ends.

{
  "type": "error",
  "what": "..."
}

Type 'error' (s2c): Server send this type of message when an error occurs on
the server.

{
  "type": "cmd",
  "cmd": "..."
}

Type 'cmd' (c2s): Client send this type of message when client want to execute
some command.

'''

def encode_msg(msg: str) -> bytes:
    bmsg = msg.encode()
    return b''.join((len(bmsg).to_bytes(4, byteorder='big'), bmsg))
