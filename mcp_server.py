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

# Load environment variables
load_dotenv()

# Initialize the FastMCP server
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
    
    # Timeout for API requests
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
        
        # Try to get API key from parameter, environment variable, or config file
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
    
    # ==================== CNEP Methods ====================
    
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
            params["cnpj"] = self._clean_document(cnpj)
        if cpf:
            params["cpf"] = self._clean_document(cpf)
        if orgao_sancionador:
            params["orgao_sancionador"] = orgao_sancionador
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim
        
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
    
    # ==================== CEPIM Methods ====================
    
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
            params["cnpj"] = self._clean_document(cnpj)
        if cpf:
            params["cpf"] = self._clean_document(cpf)
        if orgao_superior:
            params["orgao_superior"] = orgao_superior
        
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
            params["cnpj"] = self._clean_document(cnpj)
        if cpf:
            params["cpf"] = self._clean_document(cpf)
        if orgao_sancionador:
            params["orgao_sancionador"] = orgao_sancionador
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim
        
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
    
    # ==================== CEAF Methods ====================
    
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
            params["cpf"] = self._clean_document(cpf)
        if orgao_lotacao:
            params["orgao_lotacao"] = orgao_lotacao
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim
        
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
    
    # ==================== Acordos de Leniência Methods ====================
    
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
            params["nome"] = nome
        if cnpj:
            params["cnpj"] = self._clean_document(cnpj)
        if situacao:
            params["situacao"] = situacao
        if data_inicio:
            params["data_inicio"] = data_inicio
        if data_fim:
            params["data_fim"] = data_fim
        
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
    
    # ==================== Utility Methods ====================
    
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


# ==================== Example Usage ====================

def main():
    """Example usage of the Brazilian Sanctions API client"""
    
    # Option 1: Pass API key directly
    api_key = "sua_chave_api_aqui"
    try:
        client = BrazilianSanctionsAPI(api_key=api_key)
    except ValueError as e:
        print(f"Error: {e}")
        return
    
    print("Brazilian Sanctions Search Examples")
    print("="*60)
    
    # Example 1: Search CNEP by CNPJ
    print("\n1. Searching CNEP for a company (CNPJ example)...")
    result = client.search_cnep(cnpj="00.000.000/0000-00")
    client.print_results(result, "CNEP Search Results")
    
    # Example 2: Search CEIS by CPF
    print("\n2. Searching CEIS for a person (CPF example)...")
    result = client.search_ceis(cpf="000.000.000-00")
    client.print_results(result, "CEIS Search Results")
    
    # Example 3: Search all registers for a CNPJ
    print("\n3. Comprehensive search for CNPJ across all registers...")
    all_results = client.search_all(cnpj="00.000.000/0000-00")
    for register_type, result in all_results.items():
        print(f"\n{register_type.upper()}: {result.total_records} records found")
        if result.error:
            print(f"  Error: {result.error}")
    
    # Example 4: Search CEAF by CPF with date range
    print("\n4. Searching CEAF with date range...")
    result = client.search_ceaf(
        cpf="000.000.000-00",
        data_inicio="2022-01-01",
        data_fim="2023-12-31"
    )
    client.print_results(result, "CEAF Search Results (Date Range)")
    
    # Example 5: Get specific record by ID
    print("\n5. Getting specific CNEP record...")
    result = client.get_cnep_by_id("123456")
    client.print_results(result, "Specific CNEP Record")


if __name__ == "__main__":
    main()

# ==================== MCP Tools ====================

# Initialize API client (will be done lazily when needed)
_api_client = None

def get_api_client():
    """Get or create the API client instance"""
    global _api_client
    if _api_client is None:
        _api_client = BrazilianSanctionsAPI()
    return _api_client


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
        Dictionary with CNEP search results
    """
    client = get_api_client()
    result = client.search_cnep(
        cnpj=cnpj,
        cpf=cpf,
        orgao_sancionador=orgao_sancionador,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data
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
        Dictionary with CEPIM search results
    """
    client = get_api_client()
    result = client.search_cepim(
        cnpj=cnpj,
        cpf=cpf,
        orgao_superior=orgao_superior
    )
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data
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
        Dictionary with CEIS search results
    """
    client = get_api_client()
    result = client.search_ceis(
        cnpj=cnpj,
        cpf=cpf,
        orgao_sancionador=orgao_sancionador,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data
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
        Dictionary with CEAF search results
    """
    client = get_api_client()
    result = client.search_ceaf(
        cpf=cpf,
        orgao_lotacao=orgao_lotacao,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data
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
        Dictionary with leniency agreement search results
    """
    client = get_api_client()
    result = client.search_acordos_leniencia(
        nome=nome,
        cnpj=cnpj,
        situacao=situacao,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    return {
        "status_code": result.status_code,
        "total_records": result.total_records,
        "error": result.error,
        "data": result.data
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
   


# ==================== Server Startup ====================

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
