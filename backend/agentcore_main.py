"""Amazon Bedrock AgentCore Runtime entrypoint for the Strands orchestrator."""
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from wardwatch.agents.orchestrator import build_agent

app = BedrockAgentCoreApp()
agent = build_agent()


@app.entrypoint
def invoke(payload: dict) -> str:
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return "Error: 'prompt' must be a non-empty string"
    response = agent(prompt)
    return "".join(
        part.get("text", "")
        for part in response.message.get("content", [])
        if "text" in part
    )


if __name__ == "__main__":
    app.run()
