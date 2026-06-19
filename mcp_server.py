import os
import re
import time
import random
import json
import requests
from typing import Dict, List, Any, Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Literal
from mcp.server.fastmcp import FastMCP

BrazilianSanctionsData = {
    "CEIS" : {
        "full_name" : "National Register of Disreputable and Suspended Companies",
        "description" : "The CEIS serves as the primary consolidated database for individuals and companies that have been sanctioned by public entities at the federal, state, or municipal levels. Inclusion in this register means the entity is prohibited from participating in public bidding processes or entering into new contracts with the government. Penalties recorded here typically arise from violations of procurement laws, such as failure to fulfill contractual obligations or fraudulent conduct during bidding"
    },

    "CNEP" : {
        "full_name" : "National Register of Punished Companies",
        "description" : "The CNEP specifically lists legal entities that have been sanctioned under the Clean Company Act (Law No. 12.846/2013). This register tracks companies penalized for acts of corruption, bribery, or fraud against public administration, whether domestic or foreign. Unlike broader procurement sanctions, CNEP is specifically focused on anti-corruption enforcement and carries severe administrative, civil, and potentially criminal implications for the companies involved."
    },

    "CEPIM" : {
        "full_name" : "National Register of Entities Punished with Impediments",
        "description" :  "The CEPIM contains the names of non-profit entities (such as NGOs and civil society organizations) that are restricted from receiving public funds. Entities are listed in CEPIM if they have failed to meet requirements related to the use of federal transfers, such as failure to provide a proper accounting of funds received or improper execution of a partnership agreement with the federal government.",
    },

    "CEAF" : {
        "full_name" : "National Register of Companies Punished with Suspension or Prohibition",
        "description" :  "The CEAF focuses on specific administrative penalties applied to companies that have violated public administration contracts or bidding rules. While it often overlaps in function with the CEIS, it provides a dedicated repository for entities that have received specific administrative sanctions preventing them from contracting with federal agencies, helping to ensure that restricted entities are clearly identified during the due diligence process for new public spending.",
    },
        
    "LENIENCY_AGREEMENTS" : {
        "full_name" : "Acordos do leniencia OR acordos de leniencia",
        "description" : "A leniency agreement is a legal instrument established by Brazil's Clean Company Act (Law No. 12.846/2013). It allows a legal entity involved in corrupt or illicit administrative acts to cooperate with public authorities in exchange for reduced or waived sanctions.To qualify, a company must be the first to report the misconduct and provide evidence previously unknown to investigators. The agreement requires the company to cease its involvement in the illegal activity, fully compensate for any damages, and implement an effective internal compliance program. Cooperation typically involves the Office of the Comptroller General (CGU), the Office of the Attorney General (AGU), and the Public Prosecutor's Office, depending on the severity and nature of the case. Benefits include potential relief from administrative and civil penalties, such as hefty fines and disqualification from bidding on public contracts.",
    }
}

# Load Portal Tranasparecia API key
load_dotenv()

# Initialize
mcp = FastMCP("BrazillianSanctions")

"""
Brazilian Sanctions Search Module
Queries Porta da Transparência API for various sanctions records
"""

import requests
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SanctionResult:
    """Data class for sanction query results"""
    status_code: int
    data: Dict[str, Any]
    total_records: int = 0
    error: Optional[str] = None


class BrazilianSanctionsAPI:
    """
    Client for Brazilian Sanctions API
    Endpoints: CNEP, CEPIM, CEIS, CEAF, Acordos de Leniência
    
    AUTHENTICATION:
    The API key must be passed in the request header "chave-api-dados"
    Example header: {"chave-api-dados": "your_api_key"}
    
    To get your API key:
    1. Visit: https://www.portaldatransparencia.gov.br/
    2. Register and generate your API key in the developer portal
    3. Pass it to this class or set environment variable PORTAL_TRANSPARENCIA_API_KEY
    """
    
    BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"
    
    # Timeout for API requests, 20 seconds for productive enviroments
    TIMEOUT = 10
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the sanctions API client
        
        Args:
            api_key: API key for authentication. Can also be set via 
                    environment variable PORTAL_TRANSPARENCIA_API_KEY
                    
        Raises:
            ValueError: If no API key is provided or found
        """
        import os
        
        # Try to get API key from parameter, environment variable, or config file.
        self.api_key = api_key or os.getenv("PORTAL_TRANSPARENCIA_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "API key is required!\n"
                "Provide it in one of these ways:\n"
                "1. Pass to __init__: BrazilianSanctionsAPI(api_key='your_key')\n"
                "2. Set environment variable: export PORTAL_TRANSPARENCIA_API_KEY='your_key'\n"
                "3. Create .env file with: PORTAL_TRANSPARENCIA_API_KEY=your_key\n\n"
                "To get your API key, register at: https://www.portaldatransparencia.gov.br/"
            )
        
        self.session = requests.Session()
        # Try different authentication methods
        self._setup_authentication()
    
    def _setup_authentication(self):
        """Setup authentication headers for API requests
        
        Porta da Transparência expects the API key in a custom header:
        "chave-api-dados": "your_api_key"
        """
        if not self.api_key:
            return
        
        # Required header for Porta da Transparência API
        self.session.headers.update({
            "chave-api-dados": self.api_key,
            "Accept": "application/json"
        })
    
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> SanctionResult:
        """
        Make API request and return structured result
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            SanctionResult object with status and data
        """
        try:
            url = f"{self.BASE_URL}{endpoint}"
            
            # API key is now passed in header "chave-api-dados", not as parameter
            response = self.session.get(url, params=params, timeout=self.TIMEOUT)
            
            # Try to parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = {"raw_response": response.text}
            
            result = SanctionResult(
                status_code=response.status_code,
                data=data,
                error=None if response.status_code == 200 else f"HTTP {response.status_code}"
            )
            
            # Attempt to extract total records count
            if isinstance(data, dict):
                result.total_records = len(data.get("registros", []))
            elif isinstance(data, list):
                result.total_records = len(data)
            
            return result
            
        except requests.exceptions.RequestException as e:
            return SanctionResult(
                status_code=0,
                data={},
                error=f"Request failed: {str(e)}"
            )
    
    # ==================== CNEP Methods ==================== #
    
    def search_cnep(
        self,
        cnpj: Optional[str] = None,
        cpf: Optional[str] = None,
        orgao_sancionador: Optional[str] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None
    ) -> SanctionResult:
        """
        Search CNEP (National Register of Punishments)
        
        Args:
            cnpj: CNPJ of sanctioned entity (formatted or unformatted)
            cpf: CPF of sanctioned person (formatted or unformatted)
            orgao_sancionador: Sanctioning agency name
            data_inicio: Start date (YYYY-MM-DD)
            data_fim: End date (YYYY-MM-DD)
            
        Returns:
            SanctionResult with CNEP records
        """
        params = {}
        if cnpj:
            params["codigoSancionado"] = self._clean_document(cnpj)
        if cpf:
            params["codigoSancionado"] = self._clean_document(cpf)
        if orgao_sancionador:
            params["orgaoSancionador"] = orgao_sancionador
        if data_inicio:
            params["dataInicialSancao"] = data_inicio
        if data_fim:
            params["dataFinalSancao"] = data_fim
        
        return self._make_request("/cnep", params)
    
    def get_cnep_by_id(self, record_id: str) -> SanctionResult:
        """
        Get specific CNEP record by ID
        
        Args:
            record_id: CNEP record ID
            
        Returns:
            SanctionResult with single CNEP record
        """
        return self._make_request(f"/cnep/{record_id}")
    
    # ==================== CEPIM Methods ==================== #
    
    def search_cepim(
        self,
        cnpj: Optional[str] = None,
        cpf: Optional[str] = None,
        orgao_superior: Optional[str] = None
    ) -> SanctionResult:
        """
        Search CEPIM (Register of Public Employees Punished)
        
        Args:
            cnpj: CNPJ of sanctioned entity
            cpf: CPF of sanctioned person
            orgao_superior: Superior agency
            
        Returns:
            SanctionResult with CEPIM records
        """
        params = {}
        if cnpj:
            params["cnpjSancionado"] = self._clean_document(cnpj)
        if cpf:
            params["cnpjSancionado"] = self._clean_document(cpf)
        if orgao_superior:
            params["orgaoEntidade"] = orgao_superior
        
        return self._make_request("/cepim", params)
    
    def get_cepim_by_id(self, record_id: str) -> SanctionResult:
        """
        Get specific CEPIM record by ID
        
        Args:
            record_id: CEPIM record ID
            
        Returns:
            SanctionResult with single CEPIM record
        """
        return self._make_request(f"/cepim/{record_id}")
    
    # ==================== CEIS Methods ====================
    
    def search_ceis(
        self,
        cnpj: Optional[str] = None,
        cpf: Optional[str] = None,
        orgao_sancionador: Optional[str] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None
    ) -> SanctionResult:
        """
        Search CEIS (Register of Ineligible Entities)
        
        Args:
            cnpj: CNPJ of ineligible entity
            cpf: CPF of ineligible person
            orgao_sancionador: Sanctioning agency
            data_inicio: Start date (YYYY-MM-DD)
            data_fim: End date (YYYY-MM-DD)
            
        Returns:
            SanctionResult with CEIS records
        """
        params = {}
        if cnpj:
            params["codigoSancionado"] = self._clean_document(cnpj)
        if cpf:
            params["codigoSancionado"] = self._clean_document(cpf)
        if orgao_sancionador:
            params["orgaoSancionador"] = orgao_sancionador
        if data_inicio:
            params["dataInicialSancao"] = data_inicio
        if data_fim:
            params["dataFinalSancao"] = data_fim
        
        return self._make_request("/ceis", params)
    
    def get_ceis_by_id(self, record_id: str) -> SanctionResult:
        """
        Get specific CEIS record by ID
        
        Args:
            record_id: CEIS record ID
            
        Returns:
            SanctionResult with single CEIS record
        """
        return self._make_request(f"/ceis/{record_id}")
    
    # ==================== CEAF Methods ==================== # 
    
    def search_ceaf(
        self,
        cpf: Optional[str] = None,
        orgao_lotacao: Optional[str] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None
    ) -> SanctionResult:
        """
        Search CEAF (Ineligibility Register of Public Servants)
        
        Args:
            cpf: CPF of ineligible servant
            orgao_lotacao: Agency where servant works
            data_inicio: Start date (YYYY-MM-DD)
            data_fim: End date (YYYY-MM-DD)
            
        Returns:
            SanctionResult with CEAF records
        """
        params = {}
        if cpf:
            params["cpfSancionado"] = self._clean_document(cpf)
        if orgao_lotacao:
            params["orgaoLotacao"] = orgao_lotacao
        if data_inicio:
            params["dataPublicacaoInicio"] = data_inicio
        if data_fim:
            params["dataPublicacaoFim"] = data_fim
        
        return self._make_request("/ceaf", params)
    
    def get_ceaf_by_id(self, record_id: str) -> SanctionResult:
        """
        Get specific CEAF record by ID
        
        Args:
            record_id: CEAF record ID
            
        Returns:
            SanctionResult with single CEAF record
        """
        return self._make_request(f"/ceaf/{record_id}")
    
    # ==================== Acordos de Leniência Methods ==================== #
    
    def search_acordos_leniencia(
        self,
        nome: Optional[str] = None,
        cnpj: Optional[str] = None,
        situacao: Optional[str] = None,
        data_inicio: Optional[str] = None,
        data_fim: Optional[str] = None
    ) -> SanctionResult:
        """
        Search Leniency Agreements
        
        Args:
            nome: Name of sanctioned entity
            cnpj: CNPJ of sanctioned entity
            situacao: Agreement status
            data_inicio: Start date (YYYY-MM-DD)
            data_fim: End date (YYYY-MM-DD)
            
        Returns:
            SanctionResult with leniency agreement records
        """
        params = {}
        if nome:
            params["nomeSancionado"] = nome
        if cnpj:
            params["cnpjSancionado"] = self._clean_document(cnpj)
        if situacao:
            params["situacao"] = situacao
        if data_inicio:
            params["dataInicialSancao"] = data_inicio
        if data_fim:
            params["dataFinalSancao"] = data_fim
        
        return self._make_request("/acordos-leniencia", params)
    
    def get_acordo_leniencia_by_id(self, record_id: str) -> SanctionResult:
        """
        Get specific Leniency Agreement record by ID
        
        Args:
            record_id: Leniency Agreement record ID
            
        Returns:
            SanctionResult with single leniency agreement record
        """
        return self._make_request(f"/acordos-leniencia/{record_id}")
    
    # ==================== Utility Methods ==================== #
    
    @staticmethod
    def _clean_document(doc: str) -> str:
        """
        Remove common formatting characters from documents
        
        Args:
            doc: CPF or CNPJ string
            
        Returns:
            Cleaned document string
        """
        return "".join(c for c in doc if c.isdigit())
    
    def search_all(
        self,
        cnpj: Optional[str] = None,
        cpf: Optional[str] = None
    ) -> Dict[str, SanctionResult]:
        """
        Search all sanctions registers for a given CNPJ or CPF
        
        Args:
            cnpj: CNPJ to search in all registers
            cpf: CPF to search in all registers
            
        Returns:
            Dictionary with results from all sanction types
        """
        results = {}
        
        if cnpj:
            clean_cnpj = self._clean_document(cnpj)
            results["cnep"] = self.search_cnep(cnpj=clean_cnpj)
            results["cepim"] = self.search_cepim(cnpj=clean_cnpj)
            results["ceis"] = self.search_ceis(cnpj=clean_cnpj)
            results["acordos_leniencia"] = self.search_acordos_leniencia(cnpj=clean_cnpj)
        
        if cpf:
            clean_cpf = self._clean_document(cpf)
            results["cnep_cpf"] = self.search_cnep(cpf=clean_cpf)
            results["cepim_cpf"] = self.search_cepim(cpf=clean_cpf)
            results["ceis_cpf"] = self.search_ceis(cpf=clean_cpf)
            results["ceaf"] = self.search_ceaf(cpf=clean_cpf)
        
        return results
    
    def print_results(self, result: SanctionResult, title: str = "Results") -> None:
        """
        Pretty print sanction search results
        
        Args:
            result: SanctionResult object
            title: Title for output
        """
        print(f"\n{'='*60}")
        print(f"{title}")
        print(f"{'='*60}")
        print(f"Status Code: {result.status_code}")
        print(f"Total Records: {result.total_records}")
        
        if result.error:
            print(f"Error: {result.error}")
        else:
            print(f"Data:\n{json.dumps(result.data, indent=2, ensure_ascii=False)}")


# ==================== MCP Tools ==================== # 

# Initialize API client (will be done lazily when needed)
_api_client = None

def get_api_client():
    """Get or create the API client instance"""
    global _api_client
    if _api_client is None:
        _api_client = BrazilianSanctionsAPI()
    return _api_client


def extract_fields_from_records(records: List[Dict], register_type: str) -> List[Dict]:
    """
    Extract relevant fields from API records based on register type
    
    Args:
        records: List of record dictionaries from API
        register_type: Type of register (CNEP, CEPIM, CEIS, CEAF, LENIENCY_AGREEMENTS)
        
    Returns:
        List of dictionaries with extracted fields
    """
    extracted = []
    
    def safe_get(dct, *keys):
        """Safely get nested dictionary values"""
        for key in keys:
            if isinstance(dct, dict) and key in dct:
                dct = dct[key]
            else:
                return None
        return dct
    
    for record in records:
        extracted_record = {}
        
        if register_type == "CNEP":
            extracted_record = {
                "nome_sancionado": safe_get(record, "sancionado", "nome"),
                "razao_social": safe_get(record, "pessoa", "razaoSocialReceita"),
                "nome_fantasia": safe_get(record, "pessoa", "nomeFantasiaReceita"),
                "pessoa_nome": safe_get(record, "pessoa", "nome"),
                "orgao_sancionador": safe_get(record, "orgaoSancionador", "nome"),
                "orgao_sancionador_sigla": safe_get(record, "orgaoSancionador", "siglaUf"),
                "orgao_sancionador_poder": safe_get(record, "orgaoSancionador", "poder"),
                "orgao_sancionador_esfera": safe_get(record, "orgaoSancionador", "esfera"),
                "data_inicial_sancao": record.get("dataInicioSancao"),
                "data_final_sancao": record.get("dataFimSancao"),
                "data_publicacao_sancao": record.get("dataPublicacaoSancao"),
                "tipo_sancao_descricao": safe_get(record, "tipoSancao", "descricaoResumida"),
                "tipo_sancao_portal": safe_get(record, "tipoSancao", "descricaoPortal"),
                "fundamentacao": record.get("fundamentacao"),
                "valor_multa": record.get("valorMulta"),
                "numero_processo": record.get("numeroProcesso")
            }
        elif register_type == "CEPIM":
            extracted_record = {
                "nome_sancionado": safe_get(record, "pessoaJuridica", "nome"),
                "razao_social": safe_get(record, "pessoaJuridica", "razaoSocialReceita"),
                "nome_fantasia": safe_get(record, "pessoaJuridica", "nomeFantasiaReceita"),
                "orgao_superior": safe_get(record, "orgaoSuperior", "nome"),
                "orgao_superior_sigla": safe_get(record, "orgaoSuperior", "sigla"),
                "orgao_superior_poder": safe_get(record, "orgaoSuperior", "descricaoPoder"),
                "motivo": record.get("motivo"),
                "convenio_objeto": safe_get(record, "convenio", "objeto"),
                "convenio_numero": safe_get(record, "convenio", "numero")
            }
        elif register_type == "CEIS":
            extracted_record = {
                "nome_sancionado": safe_get(record, "sancionado", "nome"),
                "razao_social": safe_get(record, "pessoa", "razaoSocialReceita"),
                "nome_fantasia": safe_get(record, "pessoa", "nomeFantasiaReceita"),
                "pessoa_nome": safe_get(record, "pessoa", "nome"),
                "orgao_sancionador": safe_get(record, "orgaoSancionador", "nome"),
                "orgao_sancionador_sigla": safe_get(record, "orgaoSancionador", "siglaUf"),
                "orgao_sancionador_poder": safe_get(record, "orgaoSancionador", "poder"),
                "orgao_sancionador_esfera": safe_get(record, "orgaoSancionador", "esfera"),
                "data_inicial_sancao": record.get("dataInicioSancao"),
                "data_final_sancao": record.get("dataFimSancao"),
                "data_publicacao_sancao": record.get("dataPublicacaoSancao"),
                "tipo_sancao_descricao": safe_get(record, "tipoSancao", "descricaoResumida"),
                "tipo_sancao_portal": safe_get(record, "tipoSancao", "descricaoPortal"),
                "fundamentacao": record.get("fundamentacao"),
                "numero_processo": record.get("numeroProcesso")
            }
        elif register_type == "CEAF":
            extracted_record = {
                "nome_sancionado": safe_get(record, "punicao", "nomePunido"),
                "razao_social": safe_get(record, "pessoa", "razaoSocialReceita"),
                "nome_fantasia": safe_get(record, "pessoa", "nomeFantasiaReceita"),
                "pessoa_nome": safe_get(record, "pessoa", "nome"),
                "orgao_lotacao": safe_get(record, "orgaoLotacao", "nome"),
                "orgao_lotacao_sigla": safe_get(record, "orgaoLotacao", "sigla"),
                "orgao_lotacao_pasta": safe_get(record, "orgaoLotacao", "siglaDaPasta"),
                "uf_lotacao": safe_get(record, "ufLotacaoPessoa", "uf", "sigla"),
                "uf_lotacao_nome": safe_get(record, "ufLotacaoPessoa", "uf", "nome"),
                "data_publicacao": record.get("dataPublicacao"),
                "data_referencia": record.get("dataReferencia"),
                "tipo_punicao_descricao": safe_get(record, "tipoPunicao", "descricao"),
                "cargo_efetivo": record.get("cargoEfetivo"),
                "cargo_comissao": record.get("cargoComissao"),
                "fundamentacao": record.get("fundamentacao")
            }
        elif register_type == "LENIENCY_AGREEMENTS":
            # Extract names from sancoes array
            sancoes = record.get("sancoes", [])
            if sancoes and isinstance(sancoes, list):
                first_sancoes = sancoes[0] if isinstance(sancoes[0], dict) else {}
                extracted_record = {
                    "nome_sancionado": first_sancoes.get("nomeInformadoOrgaoResponsavel"),
                    "razao_social": first_sancoes.get("razaoSocial"),
                    "nome_fantasia": first_sancoes.get("nomeFantasia"),
                    "cnpj": first_sancoes.get("cnpjFormatado"),
                    "orgao_responsavel": record.get("orgaoResponsavel"),
                    "situacao_acordo": record.get("situacaoAcordo"),
                    "data_inicio_acordo": record.get("dataInicioAcordo"),
                    "data_fim_acordo": record.get("dataFimAcordo"),
                    "quantidade": record.get("quantidade")
                }
            else:
                extracted_record = {
                    "orgao_responsavel": record.get("orgaoResponsavel"),
                    "situacao_acordo": record.get("situacaoAcordo"),
                    "data_inicio_acordo": record.get("dataInicioAcordo"),
                    "data_fim_acordo": record.get("dataFimAcordo"),
                    "quantidade": record.get("quantidade")
                }
        
        # Add raw record for reference
        extracted_record["_raw"] = record
        extracted.append(extracted_record)
    
    return extracted


def is_still_sanctioned(data_final_sancao: Optional[str]) -> bool:
    """
    Check if sanction is still active based on end date
    
    Args:
        data_final_sancao: End date string (YYYY-MM-DD format)
        
    Returns:
        True if sanction is still active, False otherwise
    """
    if not data_final_sancao:
        return True  # No end date means still active
    
    try:
        from datetime import datetime
        end_date = datetime.strptime(data_final_sancao, "%Y-%m-%d")
        return end_date >= datetime.now()
    except (ValueError, TypeError):
        return True  # If date parsing fails, assume still active


@mcp.tool()
async def search_cnep(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None,
    orgao_sancionador: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search CNEP (National Register of Punishments)
    
    Args:
        cnpj: CNPJ of sanctioned entity (formatted or unformatted)
        cpf: CPF of sanctioned person (formatted or unformatted)
        orgao_sancionador: Sanctioning agency name
        data_inicio: Start date (YYYY-MM-DD)
        data_fim: End date (YYYY-MM-DD)
        
    Returns:
        Dictionary with CNEP search results including extracted fields
    """
    client = get_api_client()
    result = client.search_cnep(
        cnpj=cnpj,
        cpf=cpf,
        orgao_sancionador=orgao_sancionador,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    
    # Extract relevant fields from records
    records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
    extracted_records = extract_fields_from_records(records, "CNEP")
    
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data,
        "extracted_fields": extracted_records
    }


@mcp.tool()
async def search_cepim(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None,
    orgao_superior: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search CEPIM (Register of Public Employees Punished)
    
    Args:
        cnpj: CNPJ of sanctioned entity
        cpf: CPF of sanctioned person
        orgao_superior: Superior agency
        
    Returns:
        Dictionary with CEPIM search results including extracted fields
    """
    client = get_api_client()
    result = client.search_cepim(
        cnpj=cnpj,
        cpf=cpf,
        orgao_superior=orgao_superior
    )
    
    # Extract relevant fields from records
    records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
    extracted_records = extract_fields_from_records(records, "CEPIM")
    
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data,
        "extracted_fields": extracted_records
    }


@mcp.tool()
async def search_ceis(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None,
    orgao_sancionador: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search CEIS (Register of Ineligible Entities)
    
    Args:
        cnpj: CNPJ of ineligible entity
        cpf: CPF of ineligible person
        orgao_sancionador: Sanctioning agency
        data_inicio: Start date (YYYY-MM-DD)
        data_fim: End date (YYYY-MM-DD)
        
    Returns:
        Dictionary with CEIS search results including extracted fields
    """
    client = get_api_client()
    result = client.search_ceis(
        cnpj=cnpj,
        cpf=cpf,
        orgao_sancionador=orgao_sancionador,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    
    # Extract relevant fields from records
    records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
    extracted_records = extract_fields_from_records(records, "CEIS")
    
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data,
        "extracted_fields": extracted_records
    }


@mcp.tool()
async def search_ceaf(
    cpf: Optional[str] = None,
    orgao_lotacao: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search CEAF (Ineligibility Register of Public Servants)
    
    Args:
        cpf: CPF of ineligible servant
        orgao_lotacao: Agency where servant works
        data_inicio: Start date (YYYY-MM-DD)
        data_fim: End date (YYYY-MM-DD)
        
    Returns:
        Dictionary with CEAF search results including extracted fields
    """
    client = get_api_client()
    result = client.search_ceaf(
        cpf=cpf,
        orgao_lotacao=orgao_lotacao,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    
    # Extract relevant fields from records
    records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
    extracted_records = extract_fields_from_records(records, "CEAF")
    
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data,
        "extracted_fields": extracted_records
    }


@mcp.tool()
async def search_acordos_leniencia(
    nome: Optional[str] = None,
    cnpj: Optional[str] = None,
    situacao: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search Leniency Agreements
    
    Args:
        nome: Name of sanctioned entity
        cnpj: CNPJ of sanctioned entity
        situacao: Agreement status
        data_inicio: Start date (YYYY-MM-DD)
        data_fim: End date (YYYY-MM-DD)
        
    Returns:
        Dictionary with leniency agreement search results including extracted fields
    """
    client = get_api_client()
    result = client.search_acordos_leniencia(
        nome=nome,
        cnpj=cnpj,
        situacao=situacao,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    
    # Extract relevant fields from records
    records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
    extracted_records = extract_fields_from_records(records, "LENIENCY_AGREEMENTS")
    
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data,
        "extracted_fields": extracted_records
    }


@mcp.tool()
async def search_all_registers(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search all sanctions registers for a given CNPJ or CPF
    
    Args:
        cnpj: CNPJ to search in all registers
        cpf: CPF to search in all registers
        
    Returns:
        Dictionary with results from all sanction types
    """
    client = get_api_client()
    results = client.search_all(cnpj=cnpj, cpf=cpf)
    
    formatted_results = {}
    for register_name, result in results.items():
        formatted_results[register_name] = {
            "status_code": result.status_code,
            "total_records": result.total_records,
            "error": result.error,
            "data": result.data
        }
    
    return formatted_results


@mcp.tool()
async def check_entity_sanctions(cnpj: str) -> Dict[str, Any]:
    """
    Complete sanctions check for an entity across all registers
    
    Args:
        cnpj: Company CNPJ (with or without formatting)
        
    Returns:
        Dictionary with comprehensive sanction status summary
    """
    client = get_api_client()
    results = client.search_all(cnpj=cnpj)
    
    # Count total sanctions found
    total_sanctions = sum(r.total_records for r in results.values())
    
    # Compile summary
    summary = {
        "cnpj": cnpj,
        "checked_at": datetime.now().isoformat(),
        "total_sanctions_found": total_sanctions,
        "registers_checked": list(results.keys()),
        "details": {}
    }
    
    # Add details for each register
    for register_name, result in results.items():
        summary["details"][register_name] = {
            "found": result.total_records > 0,
            "count": result.total_records,
            "status_code": result.status_code,
            "has_error": result.error is not None
        }
    
    return summary


@mcp.tool()
async def batch_search(documents: List[str], doc_type: str = "cpf") -> Dict[str, Dict]:
    """
    Search multiple documents (CNPJs or CPFs) in one go
    
    Args:
        documents: List of CPFs or CNPJs
        doc_type: "cpf" or "cnpj"
        
    Returns:
        Dictionary with results for each document
    """
    client = get_api_client()
    results = {}
    
    for doc in documents:
        if doc_type.lower() == "cpf":
            all_results = client.search_all(cpf=doc)
        else:
            all_results = client.search_all(cnpj=doc)
        
        # Summarize results
        total_found = sum(r.total_records for r in all_results.values())
        results[doc] = {
            "total_sanctions": total_found,
            "has_sanctions": total_found > 0,
            "timestamp": datetime.now().isoformat()
        }
    
    return results


@mcp.tool()
async def generate_sanctions_report(results_dict: Dict[str, Any]) -> str:
    """
    Generate a formatted text report from multiple search results
    
    Args:
        results_dict: Dictionary of register_type -> result data
        
    Returns:
        Formatted report string
    """
    report = []
    report.append("=" * 70)
    report.append("BRAZILIAN SANCTIONS REPORT")
    report.append("=" * 70)
    report.append(f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    report.append("")
    
    total_sanctions = 0
    
    for register_name, result in results_dict.items():
        total_records = result.get("total_records", 0)
        status_code = result.get("status_code", 0)
        error = result.get("error")
        
        report.append(f"\n{register_name.upper()}")
        report.append("-" * 70)
        report.append(f"Records Found: {total_records}")
        report.append(f"Status: {'✓ OK' if status_code == 200 else '✗ ERROR'}")
        
        if error:
            report.append(f"Error: {error}")
        
        total_sanctions += total_records
    
    report.append("\n" + "=" * 70)
    report.append(f"TOTAL SANCTIONS FOUND: {total_sanctions}")
    report.append("=" * 70)
    
    return "\n".join(report)

@mcp.tool()
async def get_sanction_details(
    sanction_type: Literal["CEIS", "CNEP", "CEPIM", "CEAF", "LENIENCY_AGREEMENTS"]
) -> str:
    """
    Retrieves detailed information about a specific Brazilian sanction or legal instrument.
    """
    sanction = BrazilianSanctionsData.get(sanction_type)
    if not sanction:
        return f"Sanction '{sanction_type}' not found. Available types: {', '.join(BrazilianSanctionsData.keys())}"
    
    return f"{sanction['full_name']}: {sanction['description']}"


@mcp.tool()
async def identify_document_type(document: str) -> Dict[str, Any]:
    """
    Identifies whether a document is a CPF (individual) or CNPJ (company).
    This tool helps avoid confusion when working with other AIs by clearly indicating
    the document type being analyzed.
    
    Note: Leading zeros are preserved during cleaning (e.g., "000.000.000-00" is valid CPF).
    
    Args:
        document: CPF or CNPJ string (formatted or unformatted)
        
    Returns:
        Dictionary with document type information
    """
    # Clean the document by removing non-digit characters
    clean_doc = "".join(c for c in document if c.isdigit())
    
    # Determine document type based on length
    if len(clean_doc) == 11:
        doc_type = "CPF"
        description = "Cadastro de Pessoa Física (Individual Tax ID)"
        entity_type = "Individual Person"
    elif len(clean_doc) == 14:
        doc_type = "CNPJ"
        description = "Cadastro Nacional da Pessoa Jurídica (Company Tax ID)"
        entity_type = "Legal Entity/Company"
    else:
        doc_type = "UNKNOWN"
        description = "Invalid document length"
        entity_type = "Unknown"
    
    return {
        "original_document": document,
        "cleaned_document": clean_doc,
        "document_type": doc_type,
        "description": description,
        "entity_type": entity_type,
        "digit_count": len(clean_doc),
        "is_valid_format": doc_type in ["CPF", "CNPJ"]
    }


@mcp.tool()
async def check_sanction_status(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check if an entity is still sanctioned across all registers based on end dates
    
    Args:
        cnpj: Company CNPJ (with or without formatting)
        cpf: Person CPF (with or without formatting)
        
    Returns:
        Dictionary with sanction status for each register indicating if still active
    """
    client = get_api_client()
    results = client.search_all(cnpj=cnpj, cpf=cpf)
    
    status_summary = {
        "document": cnpj or cpf,
        "checked_at": datetime.now().isoformat(),
        "registers": {}
    }
    
    for register_name, result in results.items():
        if result.total_records == 0:
            status_summary["registers"][register_name] = {
                "found": False,
                "still_sanctioned": False,
                "records": []
            }
            continue
        
        records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
        register_type = register_name.replace("_cpf", "").upper()
        
        # Determine which register type to use for extraction
        if "CNEP" in register_name:
            extract_type = "CNEP"
        elif "CEPIM" in register_name:
            extract_type = "CEPIM"
        elif "CEIS" in register_name:
            extract_type = "CEIS"
        elif "CEAF" in register_name:
            extract_type = "CEAF"
        elif "LENIENT" in register_name:
            extract_type = "LENIENCY_AGREEMENTS"
        else:
            extract_type = register_name
        
        extracted = extract_fields_from_records(records, extract_type)
        
        # Check each record for active sanctions
        record_statuses = []
        any_active = False
        
        for record in extracted:
            data_final = record.get("data_final_sancao") or record.get("data_fim_acordo")
            is_active = is_still_sanctioned(data_final)
            
            if is_active:
                any_active = True
            
            record_statuses.append({
                "nome_sancionado": record.get("nome_sancionado"),
                "data_final_sancao": data_final,
                "still_sanctioned": is_active
            })
        
        status_summary["registers"][register_name] = {
            "found": True,
            "still_sanctioned": any_active,
            "total_records": len(record_statuses),
            "records": record_statuses
        }
    
    # Overall status
    all_active = any(r.get("still_sanctioned", False) for r in status_summary["registers"].values())
    status_summary["overall_still_sanctioned"] = all_active
    
    return status_summary


@mcp.tool()
async def get_sanctioning_authorities(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get information about who sanctioned the entity (orgaoSancionador)
    
    Args:
        cnpj: Company CNPJ (with or without formatting)
        cpf: Person CPF (with or without formatting)
        
    Returns:
        Dictionary with sanctioning authorities for each register
    """
    client = get_api_client()
    results = client.search_all(cnpj=cnpj, cpf=cpf)
    
    authorities_summary = {
        "document": cnpj or cpf,
        "checked_at": datetime.now().isoformat(),
        "registers": {}
    }
    
    for register_name, result in results.items():
        if result.total_records == 0:
            authorities_summary["registers"][register_name] = {
                "found": False,
                "authorities": []
            }
            continue
        
        records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
        
        # Determine which register type to use for extraction
        if "CNEP" in register_name:
            extract_type = "CNEP"
        elif "CEPIM" in register_name:
            extract_type = "CEPIM"
        elif "CEIS" in register_name:
            extract_type = "CEIS"
        elif "CEAF" in register_name:
            extract_type = "CEAF"
        elif "LENIENT" in register_name:
            extract_type = "LENIENCY_AGREEMENTS"
        else:
            extract_type = register_name
        
        extracted = extract_fields_from_records(records, extract_type)
        
        # Extract sanctioning authorities
        authorities = []
        for record in extracted:
            authority = (record.get("orgao_sancionador") or 
                        record.get("orgao_superior") or 
                        record.get("orgao_lotacao") or 
                        record.get("orgao_responsavel"))
            
            if authority:
                authorities.append({
                    "nome_sancionado": record.get("nome_sancionado") or record.get("razao_social") or record.get("nome_fantasia"),
                    "authority": authority,
                    "data_inicial": record.get("data_inicial_sancao") or record.get("data_inicio_acordo"),
                    "data_final": record.get("data_final_sancao") or record.get("data_fim_acordo")
                })
        
        authorities_summary["registers"][register_name] = {
            "found": True,
            "total_authorities": len(authorities),
            "authorities": authorities
        }
    
    return authorities_summary


@mcp.tool()
async def get_location_info(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get location/state information (UF, orgaoLotacao) for sanctioned entities
    
    Args:
        cnpj: Company CNPJ (with or without formatting)
        cpf: Person CPF (with or without formatting)
        
    Returns:
        Dictionary with location information from registers
    """
    client = get_api_client()
    results = client.search_all(cnpj=cnpj, cpf=cpf)
    
    location_summary = {
        "document": cnpj or cpf,
        "checked_at": datetime.now().isoformat(),
        "registers": {}
    }
    
    for register_name, result in results.items():
        if result.total_records == 0:
            location_summary["registers"][register_name] = {
                "found": False,
                "locations": []
            }
            continue
        
        records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
        
        # Determine which register type to use for extraction
        if "CNEP" in register_name:
            extract_type = "CNEP"
        elif "CEPIM" in register_name:
            extract_type = "CEPIM"
        elif "CEIS" in register_name:
            extract_type = "CEIS"
        elif "CEAF" in register_name:
            extract_type = "CEAF"
        elif "LENIENT" in register_name:
            extract_type = "LENIENCY_AGREEMENTS"
        else:
            extract_type = register_name
        
        extracted = extract_fields_from_records(records, extract_type)
        
        # Extract location information
        locations = []
        for record in extracted:
            uf = record.get("uf_sancionado") or record.get("uf_lotacao")
            orgao = (record.get("orgao_lotacao") or 
                    record.get("orgao_superior") or 
                    record.get("orgao_sancionador_sigla"))
            
            location_info = {
                "nome_sancionado": record.get("nome_sancionado") or record.get("razao_social") or record.get("nome_fantasia")
            }
            
            if uf:
                location_info["uf"] = uf
            if orgao:
                location_info["orgao"] = orgao
            
            if location_info.get("uf") or location_info.get("orgao"):
                locations.append(location_info)
        
        location_summary["registers"][register_name] = {
            "found": True,
            "total_locations": len(locations),
            "locations": locations
        }
    
    return location_summary


@mcp.tool()
async def get_comprehensive_overview(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a comprehensive overview with maximum information from all registers
    Includes: names, sanctioning authorities, dates, location, status, etc.
    
    Args:
        cnpj: Company CNPJ (with or without formatting)
        cpf: Person CPF (with or without formatting)
        
    Returns:
        Dictionary with comprehensive information from all registers
    """
    client = get_api_client()
    results = client.search_all(cnpj=cnpj, cpf=cpf)
    
    overview = {
        "document": cnpj or cpf,
        "document_type": "CNPJ" if cnpj else "CPF",
        "checked_at": datetime.now().isoformat(),
        "summary": {
            "total_registers_checked": len(results),
            "registers_with_sanctions": 0,
            "total_sanctions": 0,
            "still_sanctioned": False
        },
        "registers": {}
    }
    
    all_names = set()
    
    for register_name, result in results.items():
        if result.total_records == 0:
            overview["registers"][register_name] = {
                "found": False,
                "sanctions": []
            }
            continue
        
        overview["summary"]["registers_with_sanctions"] += 1
        overview["summary"]["total_sanctions"] += result.total_records
        
        records = result.data.get("registros", []) if isinstance(result.data, dict) else (result.data if isinstance(result.data, list) else [])
        
        # Determine which register type to use for extraction
        if "CNEP" in register_name:
            extract_type = "CNEP"
        elif "CEPIM" in register_name:
            extract_type = "CEPIM"
        elif "CEIS" in register_name:
            extract_type = "CEIS"
        elif "CEAF" in register_name:
            extract_type = "CEAF"
        elif "LENIENT" in register_name:
            extract_type = "LENIENCY_AGREEMENTS"
        else:
            extract_type = register_name
        
        extracted = extract_fields_from_records(records, extract_type)
        
        # Build comprehensive sanction info
        sanctions = []
        register_has_active = False
        
        for record in extracted:
            nome = record.get("nome_sancionado") or record.get("razao_social") or record.get("nome_fantasia")
            if nome:
                all_names.add(nome)
            
            data_final = record.get("data_final_sancao") or record.get("data_fim_acordo")
            is_active = is_still_sanctioned(data_final)
            
            if is_active:
                register_has_active = True
                overview["summary"]["still_sanctioned"] = True
            
            sanction_info = {
                "nome_sancionado": record.get("nome_sancionado"),
                "razao_social": record.get("razao_social"),
                "nome_fantasia": record.get("nome_fantasia"),
                "orgao_sancionador": (record.get("orgao_sancionador") or 
                                    record.get("orgao_superior") or 
                                    record.get("orgao_lotacao") or 
                                    record.get("orgao_responsavel")),
                "uf": record.get("uf_sancionado") or record.get("uf_lotacao"),
                "data_inicial_sancao": record.get("data_inicial_sancao") or record.get("data_inicio_acordo"),
                "data_final_sancao": data_final,
                "still_sanctioned": is_active,
                "tipo_sancao_descricao": record.get("tipo_sancao_descricao"),
                "tipo_punicao_descricao": record.get("tipo_punicao_descricao"),
                "situacao": record.get("situacao_acordo"),
                "fundamentacao": record.get("fundamentacao"),
                "numero_processo": record.get("numero_processo"),
                "valor_multa": record.get("valor_multa")
            }
            
            # Remove None values
            sanction_info = {k: v for k, v in sanction_info.items() if v is not None}
            
            sanctions.append(sanction_info)
        
        overview["registers"][register_name] = {
            "found": True,
            "register_type": BrazilianSanctionsData.get(extract_type, {}).get("full_name", extract_type),
            "total_sanctions": len(sanctions),
            "has_active_sanctions": register_has_active,
            "sanctions": sanctions
        }
    
    # Add all unique names found
    overview["names_found"] = list(all_names)
    
    return overview
   


# ==================== Server Startup ====================

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
