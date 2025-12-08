from app.main import BUFFER_SIZE, token_buffers  # ty:ignore[unresolved-import]


def test_token_buffers_behavior():
    token_buffers.clear()
    session = "sess1"
    for i in range(BUFFER_SIZE + 5):
        token_buffers.setdefault(session, []).append(str(i))
        if len(token_buffers[session]) > BUFFER_SIZE:
            token_buffers[session].pop(0)
    assert len(token_buffers[session]) == BUFFER_SIZE
    assert token_buffers[session][0] == "5"
    assert token_buffers[session][-1] == str(BUFFER_SIZE + 4)
