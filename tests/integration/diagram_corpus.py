"""
Corpus of diagrams used by the complex-diagram and golden tests.

    SIMPLE_CASES   small diagrams that render beautifully today; their exact
                   output is pinned by golden files so it can never regress
    COMPLEX_CASES  diagrams with many boxes and many edges; these must come
                   out *clean* (see diagram_checker.py), not byte-identical
    RANDOM_CASES   seeded pseudo-random graphs for breadth, some of them with
                   random generator options

Diagrams with group boxes mirror those three lists:

    SIMPLE_GROUP_CASES   small grouped diagrams, pinned by golden files too
    COMPLEX_GROUP_CASES  busy grouped diagrams: edges inside groups, around
                         them and through several of them, real-world
                         architectures, and groups crossed with the options
    RANDOM_GROUP_CASES   seeded random graphs with random groups and options

Every case is rendered top-to-bottom and left-to-right unless it says
otherwise, and the complex cases cross a set of graphs with every generator
option that changes the picture (shadow, rounded, compact, title, spacing,
text width, box width):

    graph families ─┐
    cycles ─────────┤
    real-world ─────┼──► COMPLEX_CASES ──► x {TB, LR} ──► one test per concern
    options matrix ─┘
                            ┏╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍┓
    the same, in groups ──► ╏  COMPLEX_GROUP_CASES  ╏ ──► the same tests, plus
                            ┗╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍┛     test_group_diagrams.py

Every case is plain RetroFlow input text plus optional generator options, so
any failing case can be pasted straight into ``FlowchartGenerator.generate``.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Tuple

Edge = Tuple[str, str]


@dataclass(frozen=True)
class Case:
    """One diagram to render."""

    name: str
    text: str
    options: Dict[str, object] = field(default_factory=dict)
    directions: Tuple[str, ...] = ("TB", "LR")
    # Drawable without any two edges crossing (a tree, a fan, a plain cycle).
    crossing_free: bool = False


def to_text(edges: Iterable[Edge], groups: Sequence[str] = ()) -> str:
    """Turn an edge list (and optional group lines) into input text."""
    return "\n".join([*groups, *(f"{s} -> {t}" for s, t in edges)])


def with_groups(text: str, *groups: str) -> str:
    """Put group definitions in front of an existing diagram."""
    return "\n".join([*groups, text.strip("\n")])


# ── graph families ──────────────────────────────────────────────────────


def fan_out(n: int) -> List[Edge]:
    return [("Hub", f"Leaf {i}") for i in range(1, n + 1)]


def fan_in(n: int) -> List[Edge]:
    return [(f"Feed {i}", "Sink") for i in range(1, n + 1)]


def hourglass(n: int) -> List[Edge]:
    """n sources -> one waist -> n sinks."""
    top = [(f"In {i}", "Waist") for i in range(1, n + 1)]
    bottom = [("Waist", f"Out {i}") for i in range(1, n + 1)]
    return top + bottom


def complete_dag(n: int) -> List[Edge]:
    """Every node points at every later node: the worst case for skip edges."""
    return [(f"N{i}", f"N{j}") for i in range(n) for j in range(i + 1, n)]


def bipartite(m: int, n: int) -> List[Edge]:
    """Every top node points at every bottom node."""
    return [(f"Top {i}", f"Bot {j}") for i in range(1, m + 1) for j in range(1, n + 1)]


def dense_layers(widths: Sequence[int]) -> List[Edge]:
    """Consecutive layers, fully connected to each other."""
    edges = []
    for layer in range(len(widths) - 1):
        for i in range(widths[layer]):
            for j in range(widths[layer + 1]):
                edges.append((f"L{layer}.{i}", f"L{layer + 1}.{j}"))
    return edges


def braid(layers: int, width: int) -> List[Edge]:
    """Each node feeds the node below it and the one below-right."""
    edges = []
    for layer in range(layers - 1):
        for i in range(width):
            edges.append((f"R{layer}C{i}", f"R{layer + 1}C{i}"))
            if i + 1 < width:
                edges.append((f"R{layer}C{i}", f"R{layer + 1}C{i + 1}"))
    return edges


def tree(depth: int, arity: int = 2) -> List[Edge]:
    """A full tree; node names encode the path from the root."""
    edges: List[Edge] = []
    level = ["T"]
    for _ in range(depth):
        next_level = []
        for parent in level:
            for child_idx in range(arity):
                child = f"{parent}{child_idx}"
                edges.append((parent, child))
                next_level.append(child)
        level = next_level
    return edges


def chain(n: int, prefix: str = "S") -> List[Edge]:
    return [(f"{prefix}{i}", f"{prefix}{i + 1}") for i in range(n - 1)]


def chain_with_skips(n: int, spans: Sequence[int]) -> List[Edge]:
    """A chain plus forward edges that jump ``span`` steps ahead."""
    edges = chain(n)
    for span in spans:
        edges += [(f"S{i}", f"S{i + span}") for i in range(n - span)]
    return edges


def chain_with_back_edges(n: int, back: Sequence[Tuple[int, int]]) -> List[Edge]:
    """A chain plus back edges given as (from_index, to_index) pairs."""
    return chain(n) + [(f"S{src}", f"S{dst}") for src, dst in back]


def ladder(rungs: int) -> List[Edge]:
    """Two parallel chains joined by cross links in both directions."""
    edges = chain(rungs, "A") + chain(rungs, "B")
    for i in range(rungs - 1):
        edges.append((f"A{i}", f"B{i + 1}"))
        edges.append((f"B{i}", f"A{i + 1}"))
    return edges


def random_graph(seed: int, nodes: int, extra: float, back_edges: int) -> List[Edge]:
    """
    A connected pseudo-random graph, identical on every Python version.

    Only ``Random.random()`` is used because its sequence is guaranteed stable
    across versions, unlike ``choice``/``sample``/``randrange``.
    """
    rng = random.Random(seed)

    def pick(limit: int) -> int:
        return int(rng.random() * limit)

    edges: List[Edge] = []
    for i in range(1, nodes):
        edges.append((f"G{pick(i)}", f"G{i}"))  # spanning tree keeps it connected
    for i in range(nodes):
        for j in range(i + 1, nodes):
            if rng.random() < extra and (f"G{i}", f"G{j}") not in edges:
                edges.append((f"G{i}", f"G{j}"))
    for _ in range(back_edges):
        src = 1 + pick(nodes - 1)
        edge = (f"G{src}", f"G{pick(src)}")
        if edge not in edges:
            edges.append(edge)
    return edges


def grid(rows: int, cols: int) -> List[Edge]:
    """A lattice: each cell points at its right and lower neighbours."""
    edges = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                edges.append((f"G{r}{c}", f"G{r}{c + 1}"))
            if r + 1 < rows:
                edges.append((f"G{r}{c}", f"G{r + 1}{c}"))
    return edges


def diamond_chain(n: int) -> List[Edge]:
    """n diamonds in a row, each closing where the next one opens."""
    edges = []
    for i in range(n):
        top, bottom = f"D{i}", f"D{i + 1}"
        edges += [(top, f"L{i}"), (top, f"R{i}"), (f"L{i}", bottom), (f"R{i}", bottom)]
    return edges


def caterpillar(n: int) -> List[Edge]:
    """A spine where every node also has one leaf hanging off it."""
    edges = chain(n, "Spine ")
    edges += [(f"Spine {i}", f"Leg {i}") for i in range(n)]
    return edges


def wheel(n: int) -> List[Edge]:
    """A hub pointing at n rim nodes, which form a directed ring."""
    edges = [("Hub", f"Rim {i}") for i in range(n)]
    edges += [(f"Rim {i}", f"Rim {(i + 1) % n}") for i in range(n)]
    return edges


def complete_digraph(n: int) -> List[Edge]:
    """Every ordered pair of distinct nodes: half of the edges point back."""
    return [(f"K{i}", f"K{j}") for i in range(n) for j in range(n) if i != j]


def butterfly(stages: int) -> List[Edge]:
    """An FFT-style butterfly network with 2**stages rows."""
    width = 2**stages
    edges = []
    for stage in range(stages):
        for row in range(width):
            partner = row ^ (1 << (stages - 1 - stage))
            edges.append((f"B{stage}.{row}", f"B{stage + 1}.{row}"))
            edges.append((f"B{stage}.{row}", f"B{stage + 1}.{partner}"))
    return edges


def parallel_chains(count: int, length: int) -> List[Edge]:
    """Separate chains side by side, with no edges between them."""
    edges = []
    for index in range(count):
        edges += chain(length, f"P{index}.")
    return edges


def feedback_layers(widths: Sequence[int]) -> List[Edge]:
    """Fully connected layers whose last layer feeds back into the first."""
    edges = dense_layers(widths)
    last = len(widths) - 1
    edges += [
        (f"L{last}.{i}", f"L0.{j}")
        for i in range(widths[last])
        for j in range(widths[0])
    ]
    return edges


def all_back_to_root(n: int) -> List[Edge]:
    """A chain in which every later node also points back at the first."""
    return chain(n) + [(f"S{i}", "S0") for i in range(1, n)]


def back_fan(n: int) -> List[Edge]:
    """A chain whose last node points back at every earlier node."""
    return chain(n) + [(f"S{n - 1}", f"S{i}") for i in range(n - 2)]


# ── real-world diagrams ─────────────────────────────────────────────────

MICROSERVICES = """
Client -> Gateway
Gateway -> Auth
Gateway -> Users
Gateway -> Orders
Gateway -> Payments
Auth -> UserDB
Users -> UserDB
Orders -> OrderDB
Orders -> Payments
Payments -> Ledger
Orders -> Queue
Queue -> Notifier
Notifier -> Email
Notifier -> SMS
Payments -> Notifier
Users -> Cache
Orders -> Cache
"""

ETL_PIPELINE = """
Data Lake -> Extract
Extract -> Validate Schema
Extract -> Retry Queue
Retry Queue -> Extract
Validate Schema -> Transform A
Validate Schema -> Transform B
Validate Schema -> Transform C
Transform A -> Merge
Transform B -> Merge
Transform C -> Merge
Merge -> Quality Check
Quality Check -> Load Warehouse
Quality Check -> Quarantine
Load Warehouse -> Update Indexes
Quarantine -> Manual Review
Manual Review -> Transform A
Manual Review -> Reject
Update Indexes -> Notify Downstream
Notify Downstream -> Complete
"""

CICD = """
Commit -> Lint
Commit -> Unit Tests
Commit -> Build
Lint -> Package
Unit Tests -> Package
Build -> Package
Package -> Deploy Staging
Deploy Staging -> Smoke Tests
Deploy Staging -> Load Tests
Smoke Tests -> Approval
Load Tests -> Approval
Approval -> Deploy Prod
Approval -> Commit
Deploy Prod -> Monitor
Monitor -> Rollback
Rollback -> Deploy Staging
Smoke Tests -> Rollback
"""

ORDER_STATE_MACHINE = """
Created -> Pending Payment
Pending Payment -> Paid
Pending Payment -> Cancelled
Pending Payment -> Pending Payment
Paid -> Packing
Paid -> Refunded
Packing -> Shipped
Packing -> Backordered
Backordered -> Packing
Backordered -> Cancelled
Shipped -> Delivered
Shipped -> Returned
Delivered -> Returned
Returned -> Refunded
Cancelled -> Refunded
Delivered -> Closed
Refunded -> Closed
"""

CONNECTION_STATES = """
Closed -> Listen
Closed -> Syn Sent
Listen -> Syn Received
Listen -> Syn Sent
Syn Sent -> Syn Received
Syn Sent -> Established
Syn Received -> Established
Syn Received -> Fin Wait
Established -> Fin Wait
Established -> Close Wait
Fin Wait -> Closing
Fin Wait -> Time Wait
Close Wait -> Last Ack
Closing -> Time Wait
Last Ack -> Closed
Time Wait -> Closed
Syn Sent -> Closed
Listen -> Closed
"""

COMPILER = """
Source -> Lexer
Lexer -> Parser
Parser -> AST
AST -> Type Checker
AST -> Symbol Table
Symbol Table -> Type Checker
Type Checker -> IR Builder
Symbol Table -> IR Builder
IR Builder -> Optimizer
Optimizer -> Optimizer
Optimizer -> Code Gen
Symbol Table -> Code Gen
Code Gen -> Assembler
Assembler -> Linker
Lexer -> Diagnostics
Parser -> Diagnostics
Type Checker -> Diagnostics
Linker -> Binary
"""

AUTH_FLOW = """
Login Page -> Check Credentials
Check Credentials -> MFA Prompt
Check Credentials -> Login Failed
Login Failed -> Login Page
Login Failed -> Account Locked
MFA Prompt -> Verify Code
Verify Code -> Create Session
Verify Code -> MFA Prompt
Verify Code -> Account Locked
Create Session -> Dashboard
Account Locked -> Support
Support -> Login Page
Dashboard -> Logout
Logout -> Login Page
"""

KUBERNETES = """
User -> DNS
DNS -> Load Balancer
Load Balancer -> Ingress
Ingress -> Web Service
Ingress -> API Service
Web Service -> Web Pod 1
Web Service -> Web Pod 2
API Service -> API Pod 1
API Service -> API Pod 2
API Service -> API Pod 3
Web Pod 1 -> API Service
Web Pod 2 -> API Service
API Pod 1 -> Postgres
API Pod 2 -> Postgres
API Pod 3 -> Postgres
API Pod 1 -> Redis
API Pod 2 -> Redis
API Pod 3 -> Redis
Postgres -> Volume
"""

ML_TRAINING = """
Raw Data -> Clean
Clean -> Split
Split -> Train Set
Split -> Val Set
Split -> Test Set
Train Set -> Train
Train -> Evaluate
Val Set -> Evaluate
Evaluate -> Tune
Tune -> Train
Evaluate -> Final Model
Test Set -> Final Eval
Final Model -> Final Eval
Final Eval -> Registry
Final Eval -> Clean
Registry -> Serve
Serve -> Monitor
Monitor -> Raw Data
"""

INCIDENT_RESPONSE = """
Alert -> Triage
Triage -> False Alarm
Triage -> Sev 3
Triage -> Sev 2
Triage -> Sev 1
Sev 1 -> Page On Call
Sev 2 -> Page On Call
Sev 3 -> Ticket
Page On Call -> Investigate
Ticket -> Investigate
Investigate -> Mitigate
Investigate -> Escalate
Escalate -> Investigate
Mitigate -> Verify
Verify -> Investigate
Verify -> Resolved
Resolved -> Postmortem
False Alarm -> Tune Alert
Postmortem -> Tune Alert
Tune Alert -> Alert
"""

DATA_PLATFORM = """
Web Events -> Kafka
Mobile Events -> Kafka
Billing DB -> CDC
CRM -> CDC
CDC -> Kafka
Kafka -> Stream Jobs
Kafka -> Raw Zone
Stream Jobs -> Feature Store
Stream Jobs -> Alerts
Raw Zone -> Batch Jobs
Batch Jobs -> Clean Zone
Clean Zone -> Warehouse
Clean Zone -> Feature Store
Warehouse -> BI
Warehouse -> Reverse ETL
Reverse ETL -> CRM
Feature Store -> Training
Feature Store -> Serving
Training -> Model Registry
Model Registry -> Serving
Serving -> Web Events
Batch Jobs -> Data Quality
Data Quality -> Alerts
Data Quality -> Raw Zone
BI -> Alerts
"""

CHECKOUT = """
Cart -> Sign In
Cart -> Guest Checkout
Sign In -> Shipping
Guest Checkout -> Shipping
Shipping -> Payment
Payment -> Review
Review -> Place Order
Review -> Cart
Review -> Shipping
Review -> Payment
Place Order -> Card Declined
Card Declined -> Payment
Place Order -> Confirmation
Confirmation -> Email Receipt
Confirmation -> Track Order
"""

MESH = """
Node A -> Node B
Node A -> Node D
Node B -> Node C
Node C -> Node D
Node B -> Node A
Node C -> Node B
Node D -> Node C
Node D -> Node A
"""

REVIEW_WORKFLOW = """
Draft -> Review
Review -> Changes Requested
Changes Requested -> Draft
Review -> Approved
Approved -> Merge
Approved -> Draft
Merge -> Deploy
Merge -> Notify
Deploy -> Notify
"""

LONG_LABELS = """
Receive incoming customer support request -> Classify request by product area
Classify request by product area -> Route to billing specialists
Classify request by product area -> Route to technical support engineers
Classify request by product area -> Route to account management
Route to billing specialists -> Resolve and close
Route to technical support engineers -> Resolve and close
Route to technical support engineers -> Escalate to engineering on call rotation
Route to account management -> Resolve and close
Escalate to engineering on call rotation -> Resolve and close
Resolve and close -> Send customer satisfaction survey
"""

MIXED_LABELS = """
A -> Extremely Long Descriptive Node Name
A -> B
Extremely Long Descriptive Node Name -> C
B -> C
B -> Another Quite Long Label Here
C -> D
Another Quite Long Label Here -> D
A -> D
"""

TWO_SUBSYSTEMS = """
Ingest -> Parse
Parse -> Store
Parse -> Reject
Reject -> Ingest
Query -> Plan
Plan -> Execute
Execute -> Store
Execute -> Cache
Cache -> Query
"""

OAUTH_FLOW = """
User -> Client App
Client App -> Authorization Server
Authorization Server -> Login Form
Login Form -> Authorization Server
Authorization Server -> Consent Screen
Consent Screen -> Authorization Server
Consent Screen -> Access Denied
Authorization Server -> Auth Code
Auth Code -> Client App
Client App -> Token Endpoint
Token Endpoint -> Access Token
Token Endpoint -> Refresh Token
Access Token -> Resource Server
Resource Server -> Protected Data
Protected Data -> Client App
Refresh Token -> Token Endpoint
Access Denied -> Client App
"""

GIT_FLOW = """
Feature Branch -> Pull Request
Pull Request -> Code Review
Code Review -> Feature Branch
Code Review -> Develop
Develop -> Release Branch
Release Branch -> QA
QA -> Release Branch
QA -> Main
Main -> Tag
Main -> Develop
Main -> Hotfix
Hotfix -> Main
Hotfix -> Develop
Tag -> Deploy
"""

PAYMENT_PROCESSING = """
Checkout -> Tokenize Card
Tokenize Card -> Fraud Check
Fraud Check -> Decline
Fraud Check -> Manual Review
Fraud Check -> Authorize
Manual Review -> Authorize
Manual Review -> Decline
Authorize -> Issuer Bank
Issuer Bank -> Approved
Issuer Bank -> Decline
Issuer Bank -> 3DS Challenge
3DS Challenge -> Issuer Bank
Approved -> Capture
Capture -> Settlement
Settlement -> Payout
Capture -> Refund
Refund -> Settlement
Decline -> Notify Customer
Payout -> Notify Customer
Decline -> Checkout
"""

HTTP_REQUEST = """
Browser -> DNS Lookup
DNS Lookup -> TCP Connect
TCP Connect -> TLS Handshake
TLS Handshake -> CDN Edge
CDN Edge -> Cache Hit
CDN Edge -> Load Balancer
Cache Hit -> Browser
Load Balancer -> App Server 1
Load Balancer -> App Server 2
App Server 1 -> Session Store
App Server 2 -> Session Store
App Server 1 -> Database
App Server 2 -> Database
App Server 1 -> Render
App Server 2 -> Render
Render -> CDN Edge
Database -> Read Replica
"""

RAFT_STATES = """
Follower -> Candidate
Candidate -> Candidate
Candidate -> Leader
Candidate -> Follower
Leader -> Follower
Leader -> Append Entries
Append Entries -> Follower
Append Entries -> Commit
Commit -> Apply
Apply -> Leader
Follower -> Follower
"""

POD_LIFECYCLE = """
Pending -> Scheduled
Scheduled -> Pulling Image
Pulling Image -> Image Pull Backoff
Image Pull Backoff -> Pulling Image
Pulling Image -> Init Containers
Init Containers -> Running
Init Containers -> Crash Loop
Running -> Ready
Ready -> Running
Running -> Crash Loop
Crash Loop -> Running
Running -> Succeeded
Running -> Failed
Ready -> Terminating
Terminating -> Succeeded
Failed -> Pending
Crash Loop -> Failed
"""

LOAN_APPROVAL = """
Application -> Identity Check
Application -> Credit Pull
Application -> Income Verification
Identity Check -> Risk Score
Credit Pull -> Risk Score
Income Verification -> Risk Score
Risk Score -> Auto Approve
Risk Score -> Auto Decline
Risk Score -> Underwriter
Underwriter -> Request Documents
Request Documents -> Income Verification
Underwriter -> Approve
Underwriter -> Decline
Auto Approve -> Offer
Approve -> Offer
Offer -> Accepted
Offer -> Expired
Accepted -> Funding
Auto Decline -> Adverse Action Notice
Decline -> Adverse Action Notice
Expired -> Application
"""

CQRS = """
Client -> Command API
Client -> Query API
Command API -> Command Handler
Command Handler -> Aggregate
Aggregate -> Event Store
Event Store -> Event Bus
Event Bus -> Projection A
Event Bus -> Projection B
Event Bus -> Saga
Saga -> Command Handler
Projection A -> Read Model A
Projection B -> Read Model B
Query API -> Read Model A
Query API -> Read Model B
Event Store -> Snapshots
Snapshots -> Aggregate
Event Bus -> Dead Letters
Dead Letters -> Event Bus
"""

MAP_REDUCE = """
Input -> Split 1
Input -> Split 2
Input -> Split 3
Split 1 -> Map 1
Split 2 -> Map 2
Split 3 -> Map 3
Map 1 -> Shuffle
Map 2 -> Shuffle
Map 3 -> Shuffle
Shuffle -> Reduce 1
Shuffle -> Reduce 2
Reduce 1 -> Output
Reduce 2 -> Output
Map 1 -> Combiner
Combiner -> Shuffle
Output -> Metrics
Map 2 -> Metrics
"""

SUPPORT_TICKET = """
New -> Triaged
Triaged -> Assigned
Triaged -> Duplicate
Triaged -> Spam
Assigned -> In Progress
In Progress -> Waiting On Customer
Waiting On Customer -> In Progress
Waiting On Customer -> Auto Closed
In Progress -> Escalated
Escalated -> In Progress
Escalated -> Engineering
Engineering -> In Progress
In Progress -> Resolved
Resolved -> Closed
Resolved -> Reopened
Reopened -> Assigned
Duplicate -> Closed
Spam -> Closed
Auto Closed -> Reopened
"""

FEATURE_ROLLOUT = """
Merge -> Build Flag
Build Flag -> Internal Dogfood
Internal Dogfood -> One Percent
One Percent -> Ten Percent
Ten Percent -> Fifty Percent
Fifty Percent -> Everyone
One Percent -> Metrics Review
Ten Percent -> Metrics Review
Fifty Percent -> Metrics Review
Metrics Review -> Kill Switch
Metrics Review -> Ten Percent
Metrics Review -> Fifty Percent
Metrics Review -> Everyone
Kill Switch -> Build Flag
Everyone -> Remove Flag
"""

ELEVATOR = """
Idle -> Doors Opening
Doors Opening -> Doors Open
Doors Open -> Doors Closing
Doors Closing -> Doors Opening
Doors Closing -> Idle
Doors Closing -> Moving Up
Doors Closing -> Moving Down
Moving Up -> Arriving
Moving Down -> Arriving
Arriving -> Doors Opening
Moving Up -> Emergency Stop
Moving Down -> Emergency Stop
Emergency Stop -> Idle
Idle -> Maintenance
Maintenance -> Idle
"""

BIG_ARCHITECTURE = """
Web -> CDN
Mobile -> CDN
Partner API -> API Gateway
CDN -> API Gateway
API Gateway -> Auth Service
API Gateway -> Rate Limiter
API Gateway -> Catalog
API Gateway -> Cart
API Gateway -> Checkout
API Gateway -> Search
API Gateway -> Accounts
Auth Service -> Identity DB
Auth Service -> Token Cache
Rate Limiter -> Token Cache
Catalog -> Catalog DB
Catalog -> Search Index
Search -> Search Index
Cart -> Cart Cache
Cart -> Catalog
Checkout -> Cart
Checkout -> Payments
Checkout -> Inventory
Checkout -> Orders
Payments -> Payment Provider
Payments -> Ledger DB
Inventory -> Inventory DB
Orders -> Orders DB
Orders -> Event Bus
Inventory -> Event Bus
Payments -> Event Bus
Event Bus -> Notifications
Event Bus -> Analytics
Event Bus -> Fulfilment
Fulfilment -> Shipping Provider
Fulfilment -> Inventory
Notifications -> Email Provider
Notifications -> Push Provider
Analytics -> Data Warehouse
Accounts -> Identity DB
Accounts -> Notifications
Data Warehouse -> Dashboards
Shipping Provider -> Fulfilment
"""

PUNCTUATED_LABELS = """
v1.0 -> v1.1 (beta)
v1.1 (beta) -> v2.0-rc1
v1.0 -> v2.0-rc1
v2.0-rc1 -> v2.0!
v2.0! -> v1.0
50% done? -> v2.0!
v1.1 (beta) -> 50% done?
x -> y
y -> x
x -> v1.0
"""

_GATHER = "Gather every requirement from every stakeholder before anything else happens"
_SPECIFY = "Write the specification document and circulate it for comment"
_SLICE = "Build the first vertical slice end to end"
_PREPARE = "Prepare the test environments and seed data"
_DEMO = "Demonstrate to stakeholders and collect their feedback"

VERY_LONG_LABELS = "\n".join(
    f"{source} -> {target}"
    for source, target in (
        (_GATHER, _SPECIFY),
        (_SPECIFY, _SLICE),
        (_SPECIFY, _PREPARE),
        (_SLICE, _DEMO),
        (_PREPARE, _DEMO),
        (_DEMO, _SPECIFY),
        (_DEMO, "Ship"),
        (_GATHER, "Ship"),
    )
)

# ── groups ──────────────────────────────────────────────────────────────

GROUPS_THREE_TIER = """
[Frontend: Web Mobile]
[Services: API Worker]
[Storage: DB Cache]
Web -> API
Mobile -> API
API -> Worker
API -> DB
API -> Cache
Worker -> DB
"""

GROUPS_WITH_CYCLE = """
[Front: Web Mobile]
[Back: API Worker DB]
Web -> API
Mobile -> API
API -> Worker
API -> DB
Worker -> DB
DB -> Web
"""

GROUPS_README = """
[API Layer: Gateway Auth]
[Data Layer: Database Cache]
Gateway -> Auth
Auth -> Database
Database -> Cache
Gateway -> Cache
"""

GROUPS_PARTIAL = """
[Pipeline: Extract Transform Load]
Source -> Extract
Extract -> Transform
Transform -> Load
Load -> Warehouse
Extract -> Errors
Transform -> Errors
Errors -> Source
"""

GROUPS_DENSE = """
[Edge: CDN WAF]
[Core: Router Auth Billing]
[Data: Primary Replica]
CDN -> WAF
WAF -> Router
Router -> Auth
Router -> Billing
Auth -> Primary
Billing -> Primary
Primary -> Replica
Auth -> Replica
Billing -> Router
"""

GROUPS_SINGLE_MEMBERS = """
[Entry: Gateway]
[Exit: Archive]
Gateway -> Parse
Gateway -> Validate
Parse -> Archive
Validate -> Archive
Archive -> Gateway
"""

GROUPS_WIDE = """
[Workers: Alpha Beta Gamma Delta]
Dispatch -> Alpha
Dispatch -> Beta
Dispatch -> Gamma
Dispatch -> Delta
Alpha -> Collect
Beta -> Collect
Gamma -> Collect
Delta -> Collect
Collect -> Dispatch
"""

GROUPS_LONG_TITLES = """
[The Customer Facing Presentation Tier: UI]
[Business Logic And Orchestration Services: Rules Flow]
UI -> Rules
UI -> Flow
Rules -> Flow
Flow -> Store
Rules -> Store
Store -> UI
"""

GROUPS_TWO_WAY_INSIDE = """
[Pair: Ping Pong]
[Judges: Left Right]
Ping -> Pong
Pong -> Ping
Ping -> Left
Pong -> Right
Left -> Right
Right -> Left
Right -> Ping
"""

GROUPS_FAR_APART_INSIDE = """
[Row: First Second Third Fourth]
First -> Second
First -> Third
First -> Fourth
Second -> Fourth
Fourth -> First
Third -> Sink
Fourth -> Sink
"""

GROUPS_SELF_LOOPS = """
[Retry: Fetch Parse]
[Done: Save]
Fetch -> Fetch
Fetch -> Parse
Parse -> Parse
Parse -> Save
Save -> Save
Save -> Fetch
"""

GROUPS_SAME_LAYER = """
[Left Team: Ann Bob]
[Right Team: Cy Di]
Lead -> Ann
Lead -> Bob
Lead -> Cy
Lead -> Di
Lead -> Solo
Ann -> Report
Bob -> Report
Cy -> Report
Di -> Report
Solo -> Report
Ann -> Cy
"""

GROUPS_EVERYTHING = """
[Sources: Web Mobile Partner]
[Ingest: Gateway Queue]
[Compute: Stream Batch]
[Serve: Warehouse Cache API]
Web -> Gateway
Mobile -> Gateway
Partner -> Gateway
Gateway -> Queue
Queue -> Stream
Queue -> Batch
Stream -> Cache
Batch -> Warehouse
Warehouse -> API
Cache -> API
Stream -> Batch
API -> Web
Batch -> Queue
"""

GROUPS_MULTI_WORD = """
[Edge Tier: Load Balancer Web Server]
[Data Tier: Primary Database Read Replica]
Load Balancer -> Web Server
Web Server -> Primary Database
Web Server -> Read Replica
Primary Database -> Read Replica
Read Replica -> Load Balancer
"""

GROUPS_CHAIN_INSIDE = """
[Assembly Line: Cut Weld Paint Pack]
Order -> Cut
Cut -> Weld
Weld -> Paint
Paint -> Pack
Pack -> Ship
Paint -> Weld
Pack -> Cut
"""

# An edge between two outsiders has to travel past a group.
GROUPS_BYPASS = """
[Review: Lint Tests Security]
Commit -> Lint
Commit -> Tests
Commit -> Security
Commit -> Release
Lint -> Release
Tests -> Release
Security -> Release
Release -> Commit
"""

# Every member talks to every other member, in both directions.
GROUPS_CLIQUE_INSIDE = "\n".join(
    [
        "[Quorum: N0 N1 N2 N3]",
        "Client -> N0",
        *(f"N{i} -> N{j}" for i in range(4) for j in range(4) if i != j),
        "N3 -> Log",
    ]
)

GROUPS_BIPARTITE = "\n".join(
    [
        "[Producers: P1 P2 P3]",
        "[Consumers: C1 C2 C3]",
        *(f"P{i} -> C{j}" for i in (1, 2, 3) for j in (1, 2, 3)),
    ]
)

# Six groups in a row, with edges that skip over one or more of them.
GROUPS_PIPELINE = """
[Ingest: Kafka Files]
[Parse: Decode Validate]
[Enrich: Geo Session]
[Store: Lake Index]
[Serve: API Reports]
[Watch: Alerts]
Kafka -> Decode
Files -> Decode
Decode -> Validate
Validate -> Geo
Validate -> Session
Geo -> Lake
Session -> Lake
Session -> Index
Lake -> API
Index -> API
Lake -> Reports
API -> Alerts
Validate -> Alerts
Kafka -> Lake
Decode -> Index
Alerts -> Kafka
Reports -> Files
"""

GROUPS_HUB_AND_SPOKES = """
[North: N1 N2 N3]
[South: S1 S2 S3]
N1 -> Hub
N2 -> Hub
N3 -> Hub
Hub -> S1
Hub -> S2
Hub -> S3
S1 -> Hub
S3 -> N1
N1 -> N3
S1 -> S3
"""

GROUPS_BUSY_MEMBER = """
[Core: Broker]
[Clients: Web Mobile Kiosk Partner]
[Sinks: Audit Metrics Archive]
Web -> Broker
Mobile -> Broker
Kiosk -> Broker
Partner -> Broker
Broker -> Audit
Broker -> Metrics
Broker -> Archive
Broker -> Broker
Archive -> Broker
Broker -> Web
"""

_COLLECT = "Collect the requirements from every stakeholder"
_AGREE = "Agree on the scope"
_BUILD = "Build the first vertical slice"
_SHOW = "Demonstrate it to the stakeholders"

GROUPS_LONG_LABELS = to_text(
    [
        (_COLLECT, _AGREE),
        (_AGREE, _BUILD),
        (_BUILD, _SHOW),
        (_SHOW, _AGREE),
        (_SHOW, "Ship"),
    ],
    [
        f"[Requirements And Planning: {_COLLECT} {_AGREE}]",
        f"[Delivery: {_BUILD} {_SHOW}]",
    ],
)

# Members that would sit in three different layers without the group.
GROUPS_ACROSS_LAYERS = """
[Saga: Reserve Charge Confirm]
Request -> Reserve
Reserve -> Charge
Charge -> Confirm
Confirm -> Receipt
Charge -> Refund
Refund -> Reserve
Request -> Receipt
"""

GROUPS_TWO_COMPONENTS = """
[Blue: B1 B2]
[Green: G1 G2 G3]
B1 -> B2
B2 -> Blue Out
G1 -> G2
G2 -> G3
G3 -> G1
Green In -> G1
"""

GROUPS_NEIGHBOURS_SWAPPED = """
[Stack: Top Middle Bottom]
Top -> Bottom
Bottom -> Middle
Middle -> Top
Top -> Top
In -> Middle
Bottom -> Out
"""

MICROSERVICES_GROUPED = with_groups(
    MICROSERVICES,
    "[Services: Auth Users Orders Payments]",
    "[Storage: UserDB OrderDB Ledger Cache]",
    "[Messaging: Queue Notifier]",
    "[Channels: Email SMS]",
)

CICD_GROUPED = with_groups(
    CICD,
    "[Checks: Lint Unit Tests Build]",
    "[Staging: Deploy Staging Smoke Tests Load Tests]",
    "[Production: Deploy Prod Monitor Rollback]",
)

KUBERNETES_GROUPED = with_groups(
    KUBERNETES,
    "[Services: Web Service API Service]",
    "[Web Pods: Web Pod 1 Web Pod 2]",
    "[API Pods: API Pod 1 API Pod 2 API Pod 3]",
    "[State: Postgres Redis Volume]",
)

DATA_PLATFORM_GROUPED = with_groups(
    DATA_PLATFORM,
    "[Sources: Web Events Mobile Events Billing DB CRM]",
    "[Lake: Raw Zone Clean Zone]",
    "[Jobs: Stream Jobs Batch Jobs]",
    "[ML: Feature Store Training Model Registry Serving]",
)

COMPILER_GROUPED = with_groups(
    COMPILER,
    "[Front End: Lexer Parser AST]",
    "[Middle End: Type Checker Symbol Table IR Builder Optimizer]",
    "[Back End: Code Gen Assembler Linker]",
)

CQRS_GROUPED = with_groups(
    CQRS,
    "[Write Side: Command API Command Handler Aggregate]",
    "[Events: Event Store Event Bus Snapshots Dead Letters]",
    "[Read Side: Projection A Projection B Read Model A Read Model B]",
)

MAP_REDUCE_GROUPED = with_groups(
    MAP_REDUCE,
    "[Splits: Split 1 Split 2 Split 3]",
    "[Mappers: Map 1 Map 2 Map 3]",
    "[Reducers: Reduce 1 Reduce 2]",
)

BIG_ARCHITECTURE_GROUPED = with_groups(
    BIG_ARCHITECTURE,
    "[Clients: Web Mobile Partner API]",
    "[Edge: CDN API Gateway]",
    "[Gatekeepers: Auth Service Rate Limiter]",
    "[Shopping: Catalog Cart Search Accounts]",
    "[Ordering: Checkout Payments Inventory Orders]",
    "[Databases: Identity DB Catalog DB Ledger DB Inventory DB Orders DB]",
    "[Async: Event Bus Notifications Analytics Fulfilment]",
    "[Third Parties: Payment Provider Shipping Provider Email Provider Push Provider]",
)

# ── generator options that change the picture ───────────────────────────

OPTION_SETS: Dict[str, Dict[str, object]] = {
    "no_shadow": {"shadow": False},
    "rounded": {"rounded": True},
    "expanded": {"compact": False},
    "titled": {"title": "System Overview"},
    "long_title": {
        "title": "An Unusually Long Title That Is Wider Than Most Small Diagrams"
    },
    "tight_spacing": {"horizontal_spacing": 4, "vertical_spacing": 1},
    "wide_spacing": {"horizontal_spacing": 24, "vertical_spacing": 8},
    "narrow_text": {"max_text_width": 6},
    "wide_text": {"max_text_width": 40},
    "big_boxes": {"min_box_width": 22},
    "small_boxes": {"min_box_width": 3},
    "plain_expanded_rounded": {
        "shadow": False,
        "compact": False,
        "rounded": True,
        "title": "All The Options",
        "horizontal_spacing": 8,
        "vertical_spacing": 2,
    },
    "tight_no_shadow": {
        "shadow": False,
        "horizontal_spacing": 2,
        "vertical_spacing": 1,
        "min_box_width": 4,
    },
}

# ── case lists ──────────────────────────────────────────────────────────

SIMPLE_CASES: List[Case] = [
    Case("two_nodes", "A -> B"),
    Case("chain_of_four", to_text(chain(4, "Step "))),
    Case("quick_start", "Start -> Process\nProcess -> Decision\nDecision -> End"),
    Case("fan_out_two", "Start -> Left\nStart -> Right"),
    Case("fan_in_two", "Left -> End\nRight -> End"),
    Case("diamond", "A -> B\nA -> C\nB -> D\nC -> D"),
    Case("small_tree", "Root -> Left\nRoot -> Right\nLeft -> Leaf A\nRight -> Leaf B"),
    Case("cycle_of_three", "A -> B\nB -> C\nC -> A"),
    Case(
        "retry_loop",
        "Fetch -> Parse\nParse -> Save\nParse -> Fetch",
        directions=("TB",),
    ),
    Case("self_loop", "A -> B\nB -> B\nB -> C", directions=("TB",)),
    Case(
        "multi_word_names",
        "User Login -> Validate Credentials\nValidate Credentials -> Access Granted",
    ),
    Case(
        "wrapped_names",
        "Collect the quarterly sales figures -> Summarize them for the board\n"
        "Summarize them for the board -> Publish",
    ),
    Case("two_chains", "A -> B\nB -> C\nX -> Y\nY -> Z"),
    Case("titled", "Build -> Test\nTest -> Deploy", {"title": "CI/CD Pipeline"}),
    Case("no_shadow", "A -> B\nA -> C\nB -> D\nC -> D", {"shadow": False}),
    Case("rounded", "A -> B\nB -> C\nC -> A", {"rounded": True}),
    Case("expanded", "A -> B\nA -> C\nB -> D\nC -> D", {"compact": False}),
]

_FAMILIES: List[Case] = [
    *(Case(f"fan_out_{n}", to_text(fan_out(n)), crossing_free=True) for n in (3, 4, 6)),
    *(Case(f"fan_in_{n}", to_text(fan_in(n)), crossing_free=True) for n in (3, 4, 6)),
    *(
        Case(f"hourglass_{n}", to_text(hourglass(n)), crossing_free=True)
        for n in (3, 5)
    ),
    *(Case(f"complete_dag_{n}", to_text(complete_dag(n))) for n in (4, 5, 6)),
    Case("bipartite_2x3", to_text(bipartite(2, 3))),
    Case("bipartite_3x3", to_text(bipartite(3, 3))),
    Case("bipartite_4x4", to_text(bipartite(4, 4))),
    Case("dense_layers_2_3_2", to_text(dense_layers((2, 3, 2)))),
    Case("dense_layers_3_3_3", to_text(dense_layers((3, 3, 3)))),
    Case("braid_4x3", to_text(braid(4, 3))),
    Case("braid_3x5", to_text(braid(3, 5))),
    Case("binary_tree_depth_3", to_text(tree(3)), crossing_free=True),
    Case("binary_tree_depth_4", to_text(tree(4)), crossing_free=True),
    Case("ternary_tree_depth_2", to_text(tree(2, 3)), crossing_free=True),
    Case("skip_one_layer", to_text(chain_with_skips(5, (2,)))),
    Case("skip_two_layers", to_text(chain_with_skips(6, (3,)))),
    Case("skip_mixed", to_text(chain_with_skips(6, (2, 4)))),
    Case("ladder_4", to_text(ladder(4))),
    Case("ladder_6", to_text(ladder(6))),
    # Larger and stranger shapes.
    *(Case(f"fan_out_{n}", to_text(fan_out(n)), crossing_free=True) for n in (8, 12)),
    *(Case(f"fan_in_{n}", to_text(fan_in(n)), crossing_free=True) for n in (8, 12)),
    Case("hourglass_8", to_text(hourglass(8)), crossing_free=True),
    Case("complete_dag_7", to_text(complete_dag(7))),
    Case("bipartite_2x5", to_text(bipartite(2, 5))),
    Case("bipartite_5x2", to_text(bipartite(5, 2))),
    Case("bipartite_5x5", to_text(bipartite(5, 5))),
    Case("dense_layers_2_4_4_2", to_text(dense_layers((2, 4, 4, 2)))),
    Case("dense_layers_4_1_4", to_text(dense_layers((4, 1, 4)))),
    Case("braid_6x4", to_text(braid(6, 4))),
    Case("binary_tree_depth_5", to_text(tree(5)), crossing_free=True),
    Case("ternary_tree_depth_3", to_text(tree(3, 3)), crossing_free=True),
    Case("chain_of_twelve", to_text(chain(12)), crossing_free=True),
    Case("skip_every_span", to_text(chain_with_skips(7, (2, 3, 4, 5)))),
    Case("ladder_8", to_text(ladder(8))),
    Case("grid_3x3", to_text(grid(3, 3))),
    Case("grid_4x5", to_text(grid(4, 5))),
    Case("diamond_chain_4", to_text(diamond_chain(4)), crossing_free=True),
    Case("caterpillar_6", to_text(caterpillar(6)), crossing_free=True),
    Case("butterfly_2", to_text(butterfly(2))),
    Case("butterfly_3", to_text(butterfly(3))),
    Case("parallel_chains_4x5", to_text(parallel_chains(4, 5)), crossing_free=True),
    Case(
        "disconnected_shapes",
        to_text(fan_out(3) + chain(4, "Q") + [("M", "N"), ("N", "M")] + tree(2)),
    ),
    Case("repeated_edges", "A -> B\nA -> B\nB -> C\nA -> C\nB -> C\nA -> C"),
]

_CYCLES: List[Case] = [
    Case("ring_of_six", to_text(chain(6) + [("S5", "S0")]), crossing_free=True),
    Case("two_way_pair", "A -> B\nB -> A", crossing_free=True),
    Case("loop_from_middle", "Fetch -> Parse\nParse -> Save\nParse -> Fetch"),
    Case("two_way_chain", to_text(chain(4) + [(b, a) for a, b in chain(4)])),
    Case("nested_loops", to_text(chain_with_back_edges(6, [(4, 1), (3, 2), (5, 0)]))),
    Case("back_edges_same_target", to_text(chain_with_back_edges(6, [(3, 0), (5, 0)]))),
    Case("back_edges_same_source", to_text(chain_with_back_edges(6, [(5, 0), (5, 2)]))),
    Case("overlapping_loops", to_text(chain_with_back_edges(6, [(3, 0), (5, 2)]))),
    Case("self_loops", "A -> A\nA -> B\nB -> B\nB -> C\nC -> C"),
    Case(
        "loop_with_fan_out",
        "Start -> Check\nCheck -> Path A\nCheck -> Path B\nCheck -> Path C\n"
        "Path A -> Join\nPath B -> Join\nPath C -> Join\nJoin -> Check\nJoin -> End",
    ),
    Case("skips_and_loops", to_text(chain_with_skips(6, (2,)) + [("S5", "S1")])),
    Case("mesh_readme", MESH),
    # More ways of going backwards.
    Case("ring_of_twelve", to_text(chain(12) + [("S11", "S0")]), crossing_free=True),
    Case("lone_self_loop", "A -> A", crossing_free=True),
    Case(
        "self_loop_hub",
        "In -> Hub\nHub -> Hub\nHub -> Out 1\nHub -> Out 2\nOut 1 -> Hub",
    ),
    Case("two_way_triangle", to_text(complete_digraph(3))),
    Case("complete_digraph_4", to_text(complete_digraph(4))),
    Case("complete_digraph_5", to_text(complete_digraph(5))),
    Case("wheel_5", to_text(wheel(5))),
    Case("wheel_8", to_text(wheel(8))),
    Case("all_back_to_root", to_text(all_back_to_root(6))),
    Case("back_fan", to_text(back_fan(7))),
    Case("feedback_layers_2_3_2", to_text(feedback_layers((2, 3, 2)))),
    Case("feedback_layers_3_3", to_text(feedback_layers((3, 3)))),
    Case(
        "two_rings_sharing_a_node",
        to_text(
            chain(4, "A") + [("A3", "A0")] + [("A0", "B1"), ("B1", "B2"), ("B2", "A0")]
        ),
    ),
    Case(
        "ring_with_chords",
        to_text(chain(8) + [("S7", "S0"), ("S0", "S4"), ("S2", "S6"), ("S6", "S1")]),
    ),
    Case(
        "loops_everywhere",
        to_text(chain(5) + [(f"S{i}", f"S{i}") for i in range(5)] + [("S4", "S0")]),
    ),
    Case("two_way_ladder", to_text(ladder(4) + [(b, a) for a, b in chain(4, "A")])),
]

_REAL_WORLD: List[Case] = [
    Case("microservices", MICROSERVICES),
    Case("etl_pipeline", ETL_PIPELINE),
    Case("cicd", CICD),
    Case("order_state_machine", ORDER_STATE_MACHINE),
    Case("connection_states", CONNECTION_STATES),
    Case("compiler", COMPILER),
    Case("auth_flow", AUTH_FLOW),
    Case("kubernetes", KUBERNETES),
    Case("ml_training", ML_TRAINING),
    Case("incident_response", INCIDENT_RESPONSE),
    Case("data_platform", DATA_PLATFORM),
    Case("checkout", CHECKOUT),
    Case("two_subsystems", TWO_SUBSYSTEMS),
    Case("oauth_flow", OAUTH_FLOW),
    Case("git_flow", GIT_FLOW),
    Case("payment_processing", PAYMENT_PROCESSING),
    Case("http_request", HTTP_REQUEST),
    Case("raft_states", RAFT_STATES),
    Case("pod_lifecycle", POD_LIFECYCLE),
    Case("loan_approval", LOAN_APPROVAL),
    Case("cqrs", CQRS),
    Case("map_reduce", MAP_REDUCE),
    Case("support_ticket", SUPPORT_TICKET),
    Case("feature_rollout", FEATURE_ROLLOUT),
    Case("elevator", ELEVATOR),
    Case("big_architecture", BIG_ARCHITECTURE),
]

# A few representative graphs, each drawn with every option set above:
# a pipeline with loops, a dense DAG, a small mesh and a state machine.
_OPTION_SUBJECTS = {
    "cicd": CICD,
    "compiler": COMPILER,
    "mesh": MESH,
    "pod_lifecycle": POD_LIFECYCLE,
    "skip_mixed": to_text(chain_with_skips(6, (2, 4))),
}

_OPTION_MATRIX: List[Case] = [
    Case(f"{subject}_{option_name}", text, dict(options))
    for subject, text in _OPTION_SUBJECTS.items()
    for option_name, options in OPTION_SETS.items()
]

_LABELS_AND_OPTIONS: List[Case] = [
    Case("long_labels", LONG_LABELS),
    Case("mixed_labels", MIXED_LABELS),
    Case("review_no_shadow", REVIEW_WORKFLOW, {"shadow": False}),
    Case("review_expanded", REVIEW_WORKFLOW, {"compact": False}),
    Case("review_rounded", REVIEW_WORKFLOW, {"rounded": True}),
    Case("review_titled", REVIEW_WORKFLOW, {"title": "Pull Request Lifecycle"}),
    Case(
        "review_tight_spacing",
        REVIEW_WORKFLOW,
        {"horizontal_spacing": 6, "vertical_spacing": 2},
    ),
    Case(
        "review_wide_spacing",
        REVIEW_WORKFLOW,
        {"horizontal_spacing": 20, "vertical_spacing": 6},
    ),
    Case("review_narrow_text", REVIEW_WORKFLOW, {"max_text_width": 8}),
    Case("review_wide_boxes", REVIEW_WORKFLOW, {"min_box_width": 24}),
    Case("microservices_no_shadow", MICROSERVICES, {"shadow": False}),
    Case("microservices_expanded", MICROSERVICES, {"compact": False}),
    Case("punctuated_labels", PUNCTUATED_LABELS),
    Case("very_long_labels", VERY_LONG_LABELS),
    Case("very_long_labels_wide_text", VERY_LONG_LABELS, {"max_text_width": 40}),
    Case("very_long_labels_narrow_text", VERY_LONG_LABELS, {"max_text_width": 9}),
    Case(
        "long_labels_expanded_no_shadow",
        LONG_LABELS,
        {"compact": False, "shadow": False},
    ),
    Case(
        "big_architecture_tight",
        BIG_ARCHITECTURE,
        {"horizontal_spacing": 4, "vertical_spacing": 1},
    ),
    Case(
        "big_architecture_titled_rounded",
        BIG_ARCHITECTURE,
        {"title": "Storefront Platform", "rounded": True},
    ),
]

# Small grouped diagrams. Like SIMPLE_CASES these are pinned by golden files:
# one group, a group and its surroundings, two or three groups in a row.
SIMPLE_GROUP_CASES: List[Case] = [
    Case("group_pair", "[Team: A B]\nA -> B"),
    Case("group_single_member", "[Core: Engine]\nInput -> Engine\nEngine -> Output"),
    Case("group_then_node", "[Stage: Build Test]\nBuild -> Test\nTest -> Deploy"),
    Case("group_fan_out_into", "[Workers: Left Right]\nStart -> Left\nStart -> Right"),
    Case("group_fan_in_from", "[Sources: A B C]\nA -> Sink\nB -> Sink\nC -> Sink"),
    Case("group_diamond_middle", "[Middle: B C]\nA -> B\nA -> C\nB -> D\nC -> D"),
    Case("group_two_way_pair", "[Loop: Fetch Parse]\nFetch -> Parse\nParse -> Fetch"),
    Case("group_self_loop", "[Retry: Job]\nStart -> Job\nJob -> Job\nJob -> Done"),
    Case("group_in_a_cycle", "[Hot Path: B]\nA -> B\nB -> C\nC -> A"),
    Case("group_all_nodes", "[Everything: A B C]\nA -> B\nB -> C\nA -> C"),
    Case("group_long_title", "[A Much Longer Group Title: X]\nX -> Y"),
    Case(
        "group_multi_word_names",
        "[Auth Flow: User Login Check Token]\n"
        "User Login -> Check Token\nCheck Token -> Home Page",
    ),
    Case("two_groups_chain", "[Front: Web]\n[Back: Api]\nWeb -> Api"),
    Case(
        "two_groups_pairs",
        "[Front: Web Mobile]\n[Back: Api Db]\nWeb -> Api\nMobile -> Api\nApi -> Db",
    ),
    Case(
        "three_groups_chain",
        "[In: Read]\n[Work: Parse Check]\n[Out: Write]\n"
        "Read -> Parse\nParse -> Check\nCheck -> Write",
    ),
    Case("groups_readme", GROUPS_README),
    Case("group_no_shadow", "[Team: A B]\nA -> B\nB -> C", {"shadow": False}),
    Case("group_rounded", "[Team: A B]\nA -> B\nB -> C", {"rounded": True}),
    Case("group_expanded", "[Team: A B]\nA -> B\nB -> C", {"compact": False}),
    Case("group_titled", "[Team: A B]\nA -> B\nB -> C", {"title": "Who Does What"}),
]

_GROUP_SHAPES: List[Case] = [
    Case("groups_three_tier", GROUPS_THREE_TIER),
    Case("groups_with_cycle", GROUPS_WITH_CYCLE),
    Case("groups_partial", GROUPS_PARTIAL),
    Case("groups_dense", GROUPS_DENSE),
    Case("groups_single_members", GROUPS_SINGLE_MEMBERS),
    Case("groups_wide", GROUPS_WIDE),
    Case("groups_long_titles", GROUPS_LONG_TITLES),
    Case("groups_two_way_inside", GROUPS_TWO_WAY_INSIDE),
    Case("groups_far_apart_inside", GROUPS_FAR_APART_INSIDE),
    Case("groups_self_loops", GROUPS_SELF_LOOPS),
    Case("groups_same_layer", GROUPS_SAME_LAYER),
    Case("groups_everything", GROUPS_EVERYTHING),
    Case("groups_multi_word", GROUPS_MULTI_WORD),
    Case("groups_chain_inside", GROUPS_CHAIN_INSIDE),
    Case("groups_bypass", GROUPS_BYPASS),
    Case("groups_clique_inside", GROUPS_CLIQUE_INSIDE),
    Case("groups_bipartite", GROUPS_BIPARTITE),
    Case("groups_pipeline", GROUPS_PIPELINE),
    Case("groups_hub_and_spokes", GROUPS_HUB_AND_SPOKES),
    Case("groups_busy_member", GROUPS_BUSY_MEMBER),
    Case("groups_long_labels", GROUPS_LONG_LABELS),
    Case("groups_across_layers", GROUPS_ACROSS_LAYERS),
    Case("groups_two_components", GROUPS_TWO_COMPONENTS),
    Case("groups_neighbours_swapped", GROUPS_NEIGHBOURS_SWAPPED),
    # Graph families with one layer (or every layer) put in a group.
    Case(
        "groups_fan_out_leaves",
        to_text(fan_out(5), ["[Leaves: Leaf 1 Leaf 2 Leaf 3 Leaf 4 Leaf 5]"]),
    ),
    Case(
        "groups_hourglass_ends",
        to_text(
            hourglass(3), ["[Inputs: In 1 In 2 In 3]", "[Outputs: Out 1 Out 2 Out 3]"]
        ),
    ),
    Case(
        "groups_dense_layers",
        to_text(
            dense_layers((2, 3, 2)),
            ["[Upper: L0.0 L0.1]", "[Middle: L1.0 L1.1 L1.2]", "[Lower: L2.0 L2.1]"],
        ),
    ),
    Case(
        "groups_ladder_rails",
        to_text(ladder(3), ["[Rung 0: A0 B0]", "[Rung 1: A1 B1]", "[Rung 2: A2 B2]"]),
    ),
    Case(
        "groups_complete_dag_halves",
        to_text(complete_dag(6), ["[Early: N0 N1 N2]", "[Late: N3 N4 N5]"]),
    ),
    Case(
        "groups_skip_chain",
        to_text(chain_with_skips(7, (2, 3)), ["[Mid: S2 S3]", "[End: S5 S6]"]),
    ),
    Case(
        "groups_back_edges_chain",
        to_text(
            chain_with_back_edges(6, [(4, 1), (5, 0), (3, 2)]),
            ["[Head: S0 S1]", "[Tail: S4 S5]"],
        ),
    ),
]

_GROUP_REAL_WORLD: List[Case] = [
    Case("microservices_grouped", MICROSERVICES_GROUPED),
    Case("cicd_grouped", CICD_GROUPED),
    Case("kubernetes_grouped", KUBERNETES_GROUPED),
    Case("data_platform_grouped", DATA_PLATFORM_GROUPED),
    Case("compiler_grouped", COMPILER_GROUPED),
    Case("cqrs_grouped", CQRS_GROUPED),
    Case("map_reduce_grouped", MAP_REDUCE_GROUPED),
    Case("big_architecture_grouped", BIG_ARCHITECTURE_GROUPED),
]

# Groups crossed with every option that moves their borders and titles.
_GROUP_OPTION_SUBJECTS = {
    "groups_dense": GROUPS_DENSE,
    "groups_everything": GROUPS_EVERYTHING,
    "groups_chain_inside": GROUPS_CHAIN_INSIDE,
    "cicd_grouped": CICD_GROUPED,
}

_GROUP_OPTION_MATRIX: List[Case] = [
    Case(f"{subject}_{option_name}", text, dict(options))
    for subject, text in _GROUP_OPTION_SUBJECTS.items()
    for option_name, options in OPTION_SETS.items()
]

COMPLEX_GROUP_CASES: List[Case] = [
    *_GROUP_SHAPES,
    *_GROUP_REAL_WORLD,
    *_GROUP_OPTION_MATRIX,
    Case(
        "big_architecture_grouped_tight",
        BIG_ARCHITECTURE_GROUPED,
        {"horizontal_spacing": 4, "vertical_spacing": 1, "shadow": False},
    ),
    Case(
        "microservices_grouped_titled_rounded",
        MICROSERVICES_GROUPED,
        {"title": "Order Platform", "rounded": True},
    ),
]

COMPLEX_CASES: List[Case] = [
    *_FAMILIES,
    *_CYCLES,
    *_REAL_WORLD,
    *_LABELS_AND_OPTIONS,
    *_OPTION_MATRIX,
]


def random_options(seed: int) -> Dict[str, object]:
    """A seeded pick of generator options (same on every Python version)."""
    rng = random.Random(seed)

    def pick(choices: Sequence[object]) -> object:
        return choices[int(rng.random() * len(choices))]

    return {
        "shadow": pick((True, True, False)),
        "rounded": pick((False, False, True)),
        "compact": pick((True, True, False)),
        "horizontal_spacing": pick((3, 6, 12, 18)),
        "vertical_spacing": pick((1, 2, 3, 5)),
        "max_text_width": pick((8, 22, 30)),
        "min_box_width": pick((4, 10, 16)),
        "title": pick((None, None, "Random Graph")),
    }


def random_groups(edges: Sequence[Edge], seed: int) -> List[str]:
    """Seeded group lines covering some of the nodes of ``edges``."""
    rng = random.Random(seed)
    nodes = list(dict.fromkeys(name for edge in edges for name in edge))
    lines: List[str] = []
    position = int(rng.random() * 3)
    while position < len(nodes) and len(lines) < 3:
        size = 1 + int(rng.random() * 3)
        members = nodes[position : position + size]
        lines.append(f"[Zone {len(lines) + 1}: {' '.join(members)}]")
        position += size + int(rng.random() * 3)
    return lines


def scattered_groups(edges: Sequence[Edge], seed: int) -> List[str]:
    """Seeded group lines whose members are picked from anywhere in the graph."""
    rng = random.Random(seed)
    free = list(dict.fromkeys(name for edge in edges for name in edge))
    lines: List[str] = []
    for _ in range(1 + int(rng.random() * 3)):
        size = min(len(free), 1 + int(rng.random() * 4))
        members = [free.pop(int(rng.random() * len(free))) for _ in range(size)]
        if members:
            lines.append(f"[Area {len(lines) + 1}: {' '.join(members)}]")
    return lines


def _random_grouped_case(seed: int) -> Case:
    edges = random_graph(300 + seed, 6 + seed % 6, 0.12, seed % 3)
    return Case(
        f"random_grouped_{seed:02d}", to_text(edges, random_groups(edges, 400 + seed))
    )


def _random_scattered_case(seed: int) -> Case:
    """Scattered groups, extra edges inside them, and random options."""
    edges = random_graph(700 + seed, 7 + seed % 7, 0.14, seed % 4)
    groups = scattered_groups(edges, 800 + seed)
    options = random_options(900 + seed) if seed % 2 else {}
    return Case(f"random_scattered_{seed:02d}", to_text(edges, groups), options)


RANDOM_CASES: List[Case] = [
    *(
        Case(
            f"random_dag_{seed:02d}",
            to_text(random_graph(seed, 6 + seed % 7, 0.12 + 0.02 * (seed % 4), 0)),
        )
        for seed in range(20)
    ),
    *(
        Case(
            f"random_cyclic_{seed:02d}",
            to_text(random_graph(100 + seed, 6 + seed % 6, 0.12, 1 + seed % 3)),
        )
        for seed in range(15)
    ),
    # Bigger and denser graphs.
    *(
        Case(
            f"random_big_dag_{seed:02d}",
            to_text(
                random_graph(500 + seed, 14 + seed % 9, 0.08 + 0.01 * (seed % 5), 0)
            ),
        )
        for seed in range(12)
    ),
    *(
        Case(
            f"random_big_cyclic_{seed:02d}",
            to_text(random_graph(600 + seed, 12 + seed % 8, 0.08, 2 + seed % 4)),
        )
        for seed in range(12)
    ),
    # Random graphs drawn with random generator options.
    *(
        Case(
            f"random_options_{seed:02d}",
            to_text(random_graph(200 + seed, 5 + seed % 8, 0.14, seed % 3)),
            random_options(seed),
        )
        for seed in range(24)
    ),
]

RANDOM_GROUP_CASES: List[Case] = [
    # Groups made of nodes that were written next to each other.
    *(_random_grouped_case(seed) for seed in range(16)),
    # Groups made of nodes from anywhere, half of them with random options.
    *(_random_scattered_case(seed) for seed in range(24)),
]

GROUP_CASES: List[Case] = [
    *SIMPLE_GROUP_CASES,
    *COMPLEX_GROUP_CASES,
    *RANDOM_GROUP_CASES,
]


def renderings(cases: Iterable[Case]) -> List[Tuple[Case, str]]:
    """Expand cases into one (case, direction) pair per rendering."""
    return [(case, direction) for case in cases for direction in case.directions]


def rendering_id(rendering: Tuple[Case, str]) -> str:
    case, direction = rendering
    return f"{case.name}-{direction}"
