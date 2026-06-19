# Brazilian Sanctions MCP Server

An MCP (Model Context Protocol) server that provides access to Brazilian sanctions databases through the Porta da Transparência API.

## Components

- **mcp_server.py** - MCP server exposing Brazilian sanctions search tools
- **main.py** - AI chatbot using LangChain with Ollama for natural language queries

## Features

- Search across 5 Brazilian sanctions registers
- A simple Natural language interface via AI chatbot (only for tests)
- Search by CNPJ, CPF, or company name
- Detailed sanction information including reasons, dates, and agencies
- Secure API key authentication
- Async-compatible tool execution

## Sanctions Registers Supported

| Register | Purpose | Search By |
|----------|---------|-----------|
| CNEP | National Register of Punishments | CNPJ, CPF, Agency, Date Range |
| CEPIM | Register of Sanctioned Public Employees | CNPJ, CPF, Superior Agency |
| CEIS | Register of Ineligible Entities | CNPJ, CPF, Agency, Date Range |
| CEAF | Ineligibility Register of Public Servants | CPF, Agency, Date Range |
| Leniency Agreements | Leniency Agreement Records | Name, CNPJ, Status, Date Range |

**Important**: Name search is only available for Leniency Agreements. The other registers (CNEP, CEIS, CEPIM, CEAF) only support CNPJ/CPF searches due to API limitations.

## API Key Configuration

**An API key is REQUIRED to use this system.**

### Get your API key:

1. Visit: https://www.portaldatransparencia.gov.br/ (Brazilian CPF is required)
2. Login or create an account
3. Go to "Minha Conta" → "API Keys" or "Desenvolvedor"
4. Generate a new API key
5. Copy the key (format: `abcd1234efgh5678ijkl9012`)

### Setup:

Create `.env` file in project root:
```
PORTAL_TRANSPARENCIA_API_KEY=your_key_here
```

**SECURITY**: Never commit your API key to version control!

## Usage

### Running the MCP Server

The MCP server can be run standalone or used by MCP clients:

```bash
python mcp_server.py
```

### Running the Chatbot

The chatbot provides a natural language interface to query sanctions databases:

```bash
python main.py
```

**Example queries:**
- "Need to know if 30.477.220/0001-71 is sanctioned by Brazil and if yes why?"
- "Search for Petrobras in leniency agreements"
- "Check if company with CNPJ 11222333000181 has any sanctions"

## MCP Server Tools

The MCP server exposes the following tools:

### search_cnep
Search CNEP (National Register of Punishments) for sanctioned entities or individuals by CNPJ or CPF.

### search_ceis
Search CEIS (Register of Ineligible Entities) for sanctioned entities or individuals by CNPJ or CPF.

### search_all_registers
Search all sanctions registers (CNEP, CEIS, CEPIM, CEAF, Acordos de Leniência) for a given CNPJ or CPF.

### search_by_name
Search Leniency Agreements (Acordos de Leniência) by entity name or CNPJ.

## Chatbot Demo

I'm testing with a local chatbot based in Ollama but the MCP as you know can be plugged to any Agentic AI:
- **LLM**: Ollama with qwen3:8b model
- **Agent**: LangChain create_agent with tool calling
- **Tools**: Custom LangChain tools wrapping the sanctions API

## Architecture

```
User Query (Natural Language)
    ↓
LangChain Agent (Ollama)
    ↓
Tool Selection & Execution
    ↓
MCP Tools / Direct API Calls
    ↓
Brazilian Sanctions API
    ↓
Detailed Sanction Information
    ↓
Natural Language Response
```

## Document Formatting

The system automatically cleans document numbers(Brazilian CPNJ or CPF). Both formatted and unformatted documents work:

```python
# These are equivalent:
"12.345.678/0001-00"
"123456780001000"
"123.456.789-66"
"12345678966"
```

## Error Handling

The system includes comprehensive error handling:
- API connection errors
- Invalid document formats
- Missing API keys
- Rate limiting
- Malformed responses

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key not found | Set PORTAL_TRANSPARENCIA_API_KEY in .env file |
| Ollama not running | Start Ollama service: `ollama serve` |
| Model not found | Pull model: `ollama pull qwen3:8b` |
| Connection timeout | Check internet connection and API status |
| No records found | Verify CNPJ/CPF format and check if entity exists |

## References

- **API Documentation**: https://api.portaldatransparencia.gov.br/swagger-ui/index.html
- **Porta da Transparência**: https://www.portaldatransparencia.gov.br/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **LangChain**: https://python.langchain.com/
- **Ollama**: https://ollama.ai/

## License

This project is provided as-is for accessing public Brazilian government data.

---

**Last Updated**: June 2026
**API Base URL**: https://api.portaldatransparencia.gov.br/api-de-dados
