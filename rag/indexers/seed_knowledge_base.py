"""
RAG Knowledge Base Seeder

Populates Qdrant Cloud collections with curated security knowledge:
MITRE ATT&CK, OWASP Top 10, NIST SP800-61, CVE highlights, CIS Benchmarks,
and a starter set of internal playbooks.

Run once after provisioning Qdrant Cloud:
    python -m rag.indexers.seed_knowledge_base
"""
from __future__ import annotations

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 dimension

KNOWLEDGE_BASE = {
    "mitre_attack": [
        {"text": "T1566 Phishing: Adversaries send malicious links or attachments to gain initial access via deception of end users.", "technique_id": "T1566", "tactic": "Initial Access"},
        {"text": "T1071 Application Layer Protocol: Adversaries communicate using OSI layer 7 protocols like HTTP/HTTPS/DNS to blend in with normal traffic for command and control.", "technique_id": "T1071", "tactic": "Command and Control"},
        {"text": "T1059 Command and Scripting Interpreter: Adversaries abuse command and script interpreters (PowerShell, bash, Python) to execute commands and scripts.", "technique_id": "T1059", "tactic": "Execution"},
        {"text": "T1053 Scheduled Task/Job: Adversaries abuse task scheduling functionality to facilitate initial or recurring execution of malicious code.", "technique_id": "T1053", "tactic": "Persistence"},
        {"text": "T1078 Valid Accounts: Adversaries obtain and abuse credentials of existing accounts for initial access, persistence, privilege escalation, or defense evasion.", "technique_id": "T1078", "tactic": "Privilege Escalation"},
        {"text": "T1055 Process Injection: Adversaries inject code into processes to evade process-based defenses and elevate privileges.", "technique_id": "T1055", "tactic": "Defense Evasion"},
        {"text": "T1003 OS Credential Dumping: Adversaries dump credentials from the OS and software to obtain account login information.", "technique_id": "T1003", "tactic": "Credential Access"},
        {"text": "T1082 System Information Discovery: Adversaries gather detailed information about the OS and hardware to shape follow-on behaviors.", "technique_id": "T1082", "tactic": "Discovery"},
        {"text": "T1021 Remote Services: Adversaries use valid accounts to log into a service for lateral movement, such as RDP or SSH.", "technique_id": "T1021", "tactic": "Lateral Movement"},
        {"text": "T1041 Exfiltration Over C2 Channel: Adversaries steal data by exfiltrating it over an existing command and control channel.", "technique_id": "T1041", "tactic": "Exfiltration"},
        {"text": "T1486 Data Encrypted for Impact: Adversaries encrypt data on target systems to interrupt availability, commonly known as ransomware.", "technique_id": "T1486", "tactic": "Impact"},
        {"text": "T1110 Brute Force: Adversaries use brute force techniques to gain access to accounts when passwords are unknown or password hashes are obtained.", "technique_id": "T1110", "tactic": "Credential Access"},
    ],
    "owasp": [
        {"text": "OWASP A01 Broken Access Control: Restrictions on what authenticated users are allowed to do are often not properly enforced.", "category": "A01"},
        {"text": "OWASP A02 Cryptographic Failures: Failures related to cryptography which often lead to sensitive data exposure.", "category": "A02"},
        {"text": "OWASP A03 Injection: User-supplied data is not validated, filtered, or sanitized, leading to SQL, NoSQL, OS, or LDAP injection.", "category": "A03"},
        {"text": "OWASP A07 Identification and Authentication Failures: Confirmation of the user's identity, authentication, and session management is critical.", "category": "A07"},
    ],
    "nist_sp800": [
        {"text": "NIST SP800-61 Incident Response Lifecycle: Preparation, Detection and Analysis, Containment Eradication and Recovery, Post-Incident Activity.", "framework": "SP800-61"},
        {"text": "NIST SP800-53 Access Control family requires organizations to limit system access to authorized users, processes, and devices.", "framework": "SP800-53"},
        {"text": "NIST Cybersecurity Framework core functions: Identify, Protect, Detect, Respond, Recover.", "framework": "CSF"},
    ],
    "cve_database": [
        {"text": "CVE entries represent publicly disclosed cybersecurity vulnerabilities. Severity is commonly scored using CVSS v3.1 across base, temporal, and environmental metrics.", "category": "general"},
    ],
    "cis_benchmarks": [
        {"text": "CIS Controls v8 IG1: Basic cyber hygiene including asset inventory, software inventory, and data protection for organizations with limited resources.", "control_set": "IG1"},
        {"text": "CIS Control 6: Access Control Management — establish and maintain access controls for enterprise assets and software.", "control_set": "Control 6"},
    ],
    "previous_incidents": [
        {"text": "Example prior incident: phishing email led to credential theft and lateral movement via RDP within 4 hours; contained by disabling compromised account and blocking C2 IP.", "category": "case_study"},
    ],
    "internal_playbooks": [
        {"text": "Playbook: Suspected Phishing — verify sender domain reputation, extract and detonate URLs in sandbox, disable affected mailbox forwarding rules, notify affected users.", "playbook": "phishing_response"},
        {"text": "Playbook: Brute Force Detected — lock affected account, force password reset, block source IP, review MFA enrollment status.", "playbook": "brute_force_response"},
        {"text": "Playbook: Ransomware Indicators — isolate affected host immediately, preserve volatile memory if possible, do not power off, engage IR retainer, check backup integrity.", "playbook": "ransomware_response"},
    ],
}


async def seed() -> None:
    if not QDRANT_URL or not QDRANT_API_KEY:
        logger.error("QDRANT_URL and QDRANT_API_KEY must be set to seed the knowledge base.")
        return

    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from sentence_transformers import SentenceTransformer

    client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    for collection, documents in KNOWLEDGE_BASE.items():
        logger.info("Seeding collection: %s (%d documents)", collection, len(documents))

        existing = await client.collection_exists(collection)
        if not existing:
            await client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Created collection: %s", collection)

        points = []
        for i, doc in enumerate(documents):
            text = doc["text"]
            embedding = embedder.encode(text, normalize_embeddings=True).tolist()
            payload = {**doc, "source": collection}
            points.append(PointStruct(id=i, vector=embedding, payload=payload))

        await client.upsert(collection_name=collection, points=points)
        logger.info("Upserted %d points into %s", len(points), collection)

    logger.info("Knowledge base seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
