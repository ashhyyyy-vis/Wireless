def process_handovers(sim_time):
    for ue in list(active_ues.values()):
        if ue.serving_cell_id is None:
            continue

        rsrp_tbl = radio.rsrp_table(ue)
        best_cid = radio.select_cell(rsrp_tbl)

        if best_cid is None or best_cid == ue.serving_cell_id:
            continue

        # Check if better than current
        curr_rsrp = rsrp_tbl.get(ue.serving_cell_id, -1e9)
        new_rsrp  = rsrp_tbl.get(best_cid, -1e9)

        if new_rsrp > curr_rsrp:
            # Try handover
            sinr = radio.sinr_db(best_cid, ue, rsrp_tbl)
            req_frac = radio.required_resource_fraction(sinr)

            if admission.try_admit(ue, best_cid, req_frac):
                admission.release(ue)
                ue.serving_cell_id = best_cid