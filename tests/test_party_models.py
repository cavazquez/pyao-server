"""Tests for Party Models."""

import time

from src.models.party import (
    MAX_LEVEL_DIFFERENCE,
    MAX_PARTY_MEMBERS,
    Party,
    PartyInvitation,
    PartyMember,
)


class TestPartyMember:
    """Test PartyMember model."""

    def test_create_party_member(self):
        """Test creating a party member."""
        member = PartyMember(
            user_id=1,
            username="TestPlayer",
            level=20
        )

        assert member.user_id == 1
        assert member.username == "TestPlayer"
        assert member.level == 20
        assert member.accumulated_exp == 0.0
        assert member.is_online is True
        assert member.last_seen > 0

    def test_add_experience(self):
        """Test adding experience to member."""
        member = PartyMember(user_id=1, username="Test", level=20)

        member.add_experience(100.5)
        assert member.accumulated_exp == 100.5

        member.add_experience(50.0)
        assert member.accumulated_exp == 150.5

    def test_add_negative_experience(self):
        """Test adding negative experience sets to 0."""
        member = PartyMember(user_id=1, username="Test", level=20)
        member.accumulated_exp = 50.0

        member.add_experience(-100.0)
        assert member.accumulated_exp == 0.0

    def test_withdraw_experience(self):
        """Test withdrawing accumulated experience."""
        member = PartyMember(user_id=1, username="Test", level=20)
        member.accumulated_exp = 150.0

        withdrawn = member.withdraw_experience()

        assert withdrawn == 150.0
        assert member.accumulated_exp == 0.0

    def test_can_receive_experience(self):
        """Test experience receiving conditions."""
        member = PartyMember(user_id=1, username="Test", level=20)

        # Online and within distance
        assert member.can_receive_experience(10) is True

        # Offline
        member.is_online = False
        assert member.can_receive_experience(10) is False

        # Online but too far
        member.is_online = True
        assert member.can_receive_experience(25) is False


class TestParty:
    """Test Party model."""

    def test_create_party(self):
        """Test creating a party."""
        party = Party(
            party_id=1,
            leader_id=1,
            leader_username="Leader"
        )

        assert party.party_id == 1
        assert party.leader_id == 1
        assert party.leader_username == "Leader"
        assert party.member_count == 1
        assert party.is_full is False
        assert 1 in party.member_ids
        assert party.is_leader(1) is True
        assert party.is_leader(2) is False

    def test_add_member_success(self):
        """Test successfully adding a member."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")

        success = party.add_member(2, "Member2", 20)

        assert success is True
        assert party.member_count == 2
        assert 2 in party.member_ids
        assert party.is_member(2) is True

    def test_add_member_full_party(self):
        """Test adding member to full party fails."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")

        # Fill party to max capacity
        for i in range(2, MAX_PARTY_MEMBERS + 1):
            party.add_member(i, f"Member{i}", 20)

        assert party.is_full is True

        # Try to add one more
        success = party.add_member(10, "Extra", 20)
        assert success is False
        assert party.member_count == MAX_PARTY_MEMBERS

    def test_add_duplicate_member(self):
        """Test adding duplicate member fails."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")
        party.add_member(2, "Member2", 20)

        success = party.add_member(2, "Member2", 20)
        assert success is False
        assert party.member_count == 2

    def test_add_member_level_difference_too_high(self):
        """Test adding member with level difference too high fails."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")
        # Update leader level to 20
        party.update_member_level(1, 20)

        # Try to add level 30 member (difference of 10 > MAX_LEVEL_DIFFERENCE)
        success = party.add_member(2, "Member2", 30)
        assert success is False
        assert party.member_count == 1

    def test_remove_member_success(self):
        """Test successfully removing a member."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")
        party.add_member(2, "Member2", 20)

        removed_member = party.remove_member(2)

        assert removed_member is not None
        assert removed_member.user_id == 2
        assert party.member_count == 1
        assert 2 not in party.member_ids

    def test_remove_nonexistent_member(self):
        """Test removing non-existent member returns None."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")

        removed_member = party.remove_member(99)

        assert removed_member is None
        assert party.member_count == 1

    def test_transfer_leadership_success(self):
        """Test successful leadership transfer."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")
        party.add_member(2, "Member2", 20)

        success = party.transfer_leadership(2)

        assert success is True
        assert party.leader_id == 2
        assert party.leader_username == "Member2"
        assert party.is_leader(2) is True
        assert party.is_leader(1) is False

    def test_transfer_leadership_non_member(self):
        """Test leadership transfer to non-member fails."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")

        success = party.transfer_leadership(99)

        assert success is False
        assert party.leader_id == 1

    def test_update_member_level(self):
        """Test updating member level."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")
        initial_sum = party.sum_elevated_levels

        success = party.update_member_level(1, 25)

        assert success is True
        assert party.get_member(1).level == 25
        assert party.sum_elevated_levels > initial_sum

    def test_update_nonexistent_member_level(self):
        """Test updating non-existent member level fails."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")

        success = party.update_member_level(99, 25)

        assert success is False

    def test_set_member_online_status(self):
        """Test setting member online status."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")

        success = party.set_member_online_status(1, False)

        assert success is True
        assert party.get_member(1).is_online is False

        # Set back online
        success = party.set_member_online_status(1, True)
        assert success is True
        assert party.get_member(1).is_online is True

    def test_distribute_experience(self):
        """Test experience distribution among members."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")
        party.update_member_level(1, 20)  # Level 20 leader
        party.add_member(2, "Member2", 20)  # Level 20 member
        party.add_member(3, "Member3", 10)  # Level 10 member

        # Mock helper functions
        def get_level(user_id):
            return {1: 20, 2: 20, 3: 10}[user_id]

        def get_position(user_id):
            return {"map": 1, "x": 10, "y": 10}  # All nearby

        def is_alive(user_id):
            return True

        distributed = party.distribute_experience(
            100, 1, 10, 10,  # 100 exp at map 1, position 10,10
            get_level, get_position, is_alive
        )

        # Should distribute to all 3 members based on their levels
        assert len(distributed) == 3
        assert all(exp > 0 for exp in distributed.values())
        assert party.total_exp_earned == 100


class TestPartyInvitation:
    """Test PartyInvitation model."""

    def test_create_invitation(self):
        """Test creating a party invitation."""
        invitation = PartyInvitation(
            party_id=1,
            inviter_id=1,
            inviter_username="Leader",
            target_id=2,
            target_username="Target"
        )

        assert invitation.party_id == 1
        assert invitation.inviter_id == 1
        assert invitation.inviter_username == "Leader"
        assert invitation.target_id == 2
        assert invitation.target_username == "Target"
        assert invitation.created_at > 0
        assert invitation.is_expired is False

    def test_invitation_expires(self):
        """Test invitation expires after timeout."""
        invitation = PartyInvitation(
            party_id=1,
            inviter_id=1,
            inviter_username="Leader",
            target_id=2,
            target_username="Target"
        )

        # Mock created_at to be 35 seconds ago
        invitation.created_at = time.time() - 35

        assert invitation.is_expired is True

    def test_invitation_not_expired(self):
        """Test fresh invitation is not expired."""
        invitation = PartyInvitation(
            party_id=1,
            inviter_id=1,
            inviter_username="Leader",
            target_id=2,
            target_username="Target"
        )

        # Mock created_at to be 10 seconds ago
        invitation.created_at = time.time() - 10

        assert invitation.is_expired is False


class TestPartyConstants:
    """Test party system constants."""

    def test_max_party_members(self):
        """Test MAX_PARTY_MEMBERS constant."""
        assert MAX_PARTY_MEMBERS == 5

    def test_max_level_difference(self):
        """Test MAX_LEVEL_DIFFERENCE constant."""
        assert MAX_LEVEL_DIFFERENCE == 7
