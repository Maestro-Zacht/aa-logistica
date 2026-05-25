from collections import defaultdict

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from corptools.models import CorporateContract, MapSystem
from eve_sde.models import SolarSystem
from .models import ContractThreshold, LogisticaConfiguration


@login_required
@permission_required("logistica.view_logistica")
def index(request):
    """Main logistics dashboard"""
    config = LogisticaConfiguration.get_solo()

    if config.aa_state:
        chars = User.objects.filter(
            profile__state=config.aa_state
        ).values_list(
            "character_ownerships__character__character_id",
            "character_ownerships__character__corporation_id",
            "character_ownerships__character__alliance_id",
        )
        assignee_ids = set()
        for char_id, corp_id, alliance_id in chars:
            if char_id:
                assignee_ids.add(char_id)
            if corp_id:
                assignee_ids.add(corp_id)
            if alliance_id:
                assignee_ids.add(alliance_id)
    else:
        assignee_ids = set()

    base_qs = CorporateContract.objects.filter(
        contract_type="item_exchange",
        status="outstanding",
        assignee_id__in=assignee_ids,
        date_expired__gt=timezone.now(),
    )

    rows = list(
        base_qs.values(
            "title",
            "start_location_name__system_id",
        )
        .annotate(count=Count("contract_id"))
        .order_by("start_location_name__system_id")
    )

    detail_qs = base_qs.select_related("issuer_name").values(
        "contract_id",
        "title",
        "issuer_id",
        "issuer_name__name",
        "price",
        "date_issued",
        "date_expired",
        "start_location_name__system_id",
    )

    detail_map = defaultdict(list)
    for c in detail_qs:
        detail_map[(c["start_location_name__system_id"], c["title"] or "")].append(c)

    thresholds = list(ContractThreshold.objects.select_related("solar_system").all())

    # Build system name lookup for all system IDs present in rows and thresholds
    system_ids = {r["start_location_name__system_id"] for r in rows if r["start_location_name__system_id"]}
    system_ids.update(t.solar_system_id for t in thresholds)
    system_name_map = {ms.pk: ms.name for ms in MapSystem.objects.filter(pk__in=system_ids)}

    def _find_threshold(system_id, title):
        return next(
            (t for t in thresholds if t.solar_system_id == system_id and t.matches_title(title)),
            None,
        )

    def _place_row(by_location, system_name, row):
        groups = by_location.setdefault(system_name, {"prefixed": [], "unprefixed": []})
        bucket = "prefixed" if (row["title"] or "").startswith("[") else "unprefixed"
        groups[bucket].append(row)

    by_location = {}
    covered_thresholds = set()
    for row in rows:
        system_id = row["start_location_name__system_id"]
        title = row["title"] or ""
        threshold = _find_threshold(system_id, title)
        if threshold:
            covered_thresholds.add(threshold.pk)
        row["threshold"] = threshold.minimum_count if threshold else None
        row["below_threshold"] = threshold is not None and row["count"] < threshold.minimum_count
        row["contracts"] = detail_map.get((system_id, title), [])
        _place_row(by_location, system_name_map.get(system_id) or "Unknown System", row)

    # Add zero-count rows for thresholds with no matching contracts
    for t in thresholds:
        if t.pk not in covered_thresholds:
            row = {"title": t.title, "count": 0, "threshold": t.minimum_count, "below_threshold": True, "contracts": []}
            _place_row(by_location, t.solar_system.name, row)

    for groups in by_location.values():
        for rows_list in groups.values():
            rows_list.sort(key=lambda r: (r["title"] or "").lower())

    threshold_only = request.GET.get("threshold_only") == "1"
    if threshold_only:
        by_location = {
            loc: {"prefixed": [r for r in groups["prefixed"] if r["threshold"] is not None],
                  "unprefixed": [r for r in groups["unprefixed"] if r["threshold"] is not None]}
            for loc, groups in by_location.items()
            if any(r["threshold"] is not None for g in groups.values() for r in g)
        }

    context = {
        "title": "Logistica",
        "by_location": by_location,
        "total": base_qs.count(),
        "threshold_only": threshold_only,
    }
    return render(request, "logistica/index.html", context)


@login_required
@permission_required("logistica.manage_contract_thresholds")
def threshold_list(request):
    """List and manage contract thresholds."""
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            system_id = request.POST.get("solar_system")
            title = request.POST.get("title", "").strip()
            match_type = request.POST.get("match_type", ContractThreshold.MATCH_EXACT)
            minimum_count = request.POST.get("minimum_count")
            if system_id and title and minimum_count:
                system = get_object_or_404(SolarSystem, pk=system_id)
                ContractThreshold.objects.create(
                    solar_system=system,
                    title=title,
                    match_type=match_type,
                    minimum_count=int(minimum_count),
                )
                messages.success(request, f"Threshold added for \"{title}\".")
            else:
                messages.error(request, "All fields are required.")

        elif action == "delete":
            threshold_id = request.POST.get("threshold_id")
            threshold = get_object_or_404(ContractThreshold, pk=threshold_id)
            threshold.delete()
            messages.success(request, f"Threshold \"{threshold.title}\" deleted.")

        return redirect("logistica:thresholds")

    thresholds = ContractThreshold.objects.select_related("solar_system").all()
    threshold_system_ids = set(thresholds.values_list("solar_system_id", flat=True))
    systems = MapSystem.objects.order_by("name")
    context = {
        "title": "Contract Thresholds",
        "thresholds": thresholds,
        "systems": systems,
        "threshold_system_ids": threshold_system_ids,
        "match_choices": ContractThreshold.MATCH_CHOICES,
    }
    return render(request, "logistica/thresholds.html", context)
