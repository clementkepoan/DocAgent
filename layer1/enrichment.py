import inflection
import re
from typing import Dict, Any

class ChunkEnricher:
    """Enrich code chunks with natural language context for embeddings"""
    
    def __init__(self):
        # Common acronyms to preserve
        self.acronyms = {
            "api", "http", "url", "uuid", "id", "db", "sql", "json", 
            "xml", "html", "css", "js", "jwt", "oauth", "rest"
        }

        # Customize this template based on your codebase style
        self.template = (
            "A {chunk_type} named '{name}' defined in file '{file_path}' "
            "at line {start_line}. "
            "{docstring_summary} "
            "This {chunk_type} {purpose}."
        )
    
    def enrich(self, chunk: Dict[str, Any]) -> str:
        # Normalize identifiers
        name_norm = self._normalize_identifier(chunk["name"])
        
        # Build parts
        parts = [
            f"A {chunk['entity_type']} named '{name_norm}' at line {chunk['start_line']} in module '{chunk['file_path']}' located in folder '{chunk['folder_path']}'.",
        ]
        
        # Add parent context
        if chunk.get("parent_context"):
            parts.append(f"This is nested in {chunk['parent_context']}.")

        if chunk["parent_class"]:
            parts.append(f"This method belongs to class '{chunk['parent_class']}'.")
        
        # Add docstring
        if chunk.get("docstring"):
            first_line = chunk["docstring"].strip().split("\n")[0]
            parts.append(f"Docstring: {first_line}")
        
        # Add imports for context
        if chunk.get("imports"):
            import_list = ", ".join(chunk["imports"][:3])
            parts.append(f"File imports: {import_list}")
        
        # Add purpose/responsibility
        if chunk["type"] == "class_definition":
            parts.append(self._extract_class_responsibility(chunk))
        else:
            purpose = self._infer_purpose(chunk["name"], chunk["type"])
            parts.append(f"This {chunk['type'].replace('_', ' ')} {purpose}.")
        
        # Join with spaces
        enriched = " ".join(parts)
        
        # Clean up whitespace
        return " ".join(enriched.split())
    
    def _infer_purpose(self, name: str, chunk_type: str) -> str:
        """Simple heuristic to guess purpose from naming conventions"""
        name_lower = name.lower()
        
        if chunk_type == "function":
            if "get" in name_lower or "fetch" in name_lower:
                return "retrieves data"
            elif "set" in name_lower or "update" in name_lower:
                return "modifies data"
            elif "calc" in name_lower or "compute" in name_lower:
                return "performs a calculation"
            elif "validate" in name_lower or "check" in name_lower:
                return "validates input"
            elif "handle" in name_lower or "process" in name_lower:
                return "handles a specific operation"
        
        return f"implements {chunk_type} logic"
    
    def _normalize_identifier(self, identifier: str) -> str:
        """Convert code identifiers to natural language, preserving acronyms"""
        # Split camelCase: HTTPClient -> HTTP Client
        identifier = re.sub(
            r'([a-z])([A-Z])', 
            r'\1 \2', 
            identifier
        )
        
        # Handle snake_case: calculate_total_price -> calculate total price
        identifier = identifier.replace("_", " ")
        
        # Preserve acronyms: http client -> HTTP client, get api key -> get API key
        words = identifier.split()
        result = []
        for word in words:
            if word.lower() in self.acronyms:
                result.append(word.upper())
            else:
                result.append(word)
        
        return " ".join(result)
    
    def _extract_class_responsibility(self, chunk: Dict[str, Any]) -> str:
        """Generate a useful class description based on its methods"""
        if not chunk.get("methods"):
            return f"This class implements {chunk['name']} functionality."
        
        # Summarize method purposes
        method_purposes = []
        for method in chunk["methods"][:3]:  # Top 3 methods
            purpose = self._infer_purpose(method, "function_definition")
            method_purposes.append(f"{method} ({purpose})")
        
        if method_purposes:
            return (f"This class provides {chunk['name']} functionality with methods "
                    f"including: {', '.join(method_purposes)}.")
        
        return f"This class implements {chunk['name']}."